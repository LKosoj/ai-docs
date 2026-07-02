"""`ai-docs watch` — watch source tree, regenerate docs on change with debouncing.

Uses `watchdog` (optional dependency). Pattern:
  1. On fs changes under --source, restart a debounce timer.
  2. Ignore generated docs/cache/site artifacts to avoid self-trigger loops.
  3. When the timer fires, run the same pipeline as `ai-docs gen`.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .cli_common import close_llm, prepare_run_context
from .generator import generate_docs
from .utils import is_url


_GENERATED_OUTPUT_FILES = {"mkdocs.yml"}
_GENERATED_OUTPUT_DIRS = {".ai-docs", "ai_docs_site"}
_ALLOWED_HIDDEN_DIRS = {".github"}


def should_watch_path(
    path: Path,
    source_root: Path,
    output_root: Path,
    cache_dir: Path,
    ignore_readme: bool = False,
) -> bool:
    """Return True when a filesystem event should trigger documentation regen."""
    path = Path(path).expanduser().resolve()
    source_root = Path(source_root).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    cache_dir_path = Path(cache_dir).expanduser()
    if not cache_dir_path.is_absolute():
        cache_dir_path = output_root / cache_dir_path
    cache_dir_path = cache_dir_path.resolve()

    try:
        source_rel = path.relative_to(source_root)
    except ValueError:
        return False

    source_parts = source_rel.parts
    if any(part.startswith(".") and part not in _ALLOWED_HIDDEN_DIRS for part in source_parts[:-1]):
        return False

    try:
        output_rel = path.relative_to(output_root)
    except ValueError:
        return True

    output_parts = output_rel.parts
    if len(output_parts) == 1 and output_parts[0] in _GENERATED_OUTPUT_FILES:
        return False
    if ignore_readme and len(output_parts) == 1 and output_parts[0] == "README.md":
        return False
    if output_parts and output_parts[0] in _GENERATED_OUTPUT_DIRS:
        return False
    if path == cache_dir_path or cache_dir_path in path.parents:
        return False
    return True


def _regen(args: argparse.Namespace) -> None:
    context = prepare_run_context(args)
    llm = context.llm
    try:
        generate_docs(
            files=context.scan_result.files,
            output_root=context.output_root,
            cache_dir=context.output_root / args.cache_dir,
            llm=llm,
            language=args.language,
            write_readme_flag=args.readme or not args.mkdocs,
            write_mkdocs=args.mkdocs or not args.readme,
            use_cache=not args.no_cache,
            threads=context.threads,
            local_site=context.local_site,
            force=False,
            generation_config=context.generation_config,
        )
    finally:
        close_llm(llm)
        if is_url(args.source):
            shutil.rmtree(context.scan_result.root, ignore_errors=True)


class _Debouncer:
    def __init__(self, delay: float, fn):
        self._delay = delay
        self._fn = fn
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._pending = False

    def bump(self) -> None:
        with self._lock:
            if self._running:
                self._pending = True
                return
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._delay, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
            if self._running:
                self._pending = True
                return
            self._running = True
        while True:
            try:
                self._fn()
            except Exception as exc:  # noqa: BLE001
                print(f"[ai-docs watch] regeneration failed: {exc}", file=sys.stderr)
            with self._lock:
                if self._pending:
                    self._pending = False
                    continue
                self._running = False
                return

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending = False


def run_watch(args: argparse.Namespace) -> int:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print(
            "[ai-docs watch] requires the `watchdog` package. "
            "Install via: pip install watchdog",
        )
        return 2

    if is_url(args.source):
        print("[ai-docs watch] URL sources are not supported")
        return 2

    root = Path(args.source).expanduser().resolve()
    if not root.exists():
        print(f"[ai-docs watch] source not found: {root}")
        return 2

    output_root = Path(args.output).expanduser().resolve() if args.output else root
    cache_dir = output_root / args.cache_dir
    ignore_readme = (args.readme or not args.mkdocs) and not (output_root / "README.md").exists()

    def _do_regen():
        print("[ai-docs watch] change detected — regenerating…")
        start = time.monotonic()
        _regen(args)
        print(f"[ai-docs watch] regen done in {time.monotonic() - start:.1f}s")

    debouncer = _Debouncer(args.debounce, _do_regen)

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event):  # noqa: D401
            if event.is_directory:
                return
            path = Path(event.src_path).resolve()
            if not should_watch_path(path, root, output_root, cache_dir, ignore_readme=ignore_readme):
                return
            debouncer.bump()

    observer = Observer()
    observer.schedule(_Handler(), str(root), recursive=True)
    observer.start()

    print(f"[ai-docs watch] watching {root} (debounce={args.debounce}s). Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[ai-docs watch] stopping…")
    finally:
        debouncer.cancel()
        observer.stop()
        observer.join(timeout=5.0)
    return 0
