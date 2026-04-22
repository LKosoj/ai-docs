"""`ai-docs watch` — watch source tree, regenerate docs on change with debouncing.

Uses `watchdog` (optional dependency). Pattern:
  1. Scan once at startup, persist baseline.
  2. On any fs change under --source, restart a debounce timer.
  3. When the timer fires, run the same pipeline as `ai-docs gen`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Optional, Set

from .generator import generate_docs
from .llm import from_env
from .prompts import configure as configure_prompts, load_prompt_overrides
from .scanner import scan_source
from .site_config import configure_source_url, load_source_url
from .utils import is_url


def _regen(args: argparse.Namespace, llm) -> None:
    include: Optional[Set[str]] = set(args.include) if args.include else None
    exclude: Optional[Set[str]] = set(args.exclude) if args.exclude else None
    threads = max(1, args.threads or int(os.getenv("AI_DOCS_THREADS", "5")))
    env_local_site = os.getenv("AI_DOCS_LOCAL_SITE", "false").strip().lower() in {"1", "true", "yes", "y"}
    local_site = args.local_site or env_local_site

    scan_result = scan_source(
        args.source,
        include=include,
        exclude=exclude,
        max_size=args.max_size,
        workers=threads,
    )
    prompt_overrides = load_prompt_overrides(scan_result.root)
    configure_prompts(prompt_overrides)
    configure_source_url(load_source_url(scan_result.root))

    output_root = Path(args.output).expanduser().resolve() if args.output else scan_result.root
    output_root.mkdir(parents=True, exist_ok=True)

    generate_docs(
        files=scan_result.files,
        output_root=output_root,
        cache_dir=output_root / args.cache_dir,
        llm=llm,
        language=args.language,
        write_readme_flag=args.readme or not args.mkdocs,
        write_mkdocs=args.mkdocs or not args.readme,
        use_cache=not args.no_cache,
        threads=threads,
        local_site=local_site,
        force=False,
    )

    if is_url(args.source):
        shutil.rmtree(scan_result.root, ignore_errors=True)


class _Debouncer:
    def __init__(self, delay: float, fn):
        self._delay = delay
        self._fn = fn
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def bump(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._delay, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        try:
            self._fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[ai-docs watch] regeneration failed: {exc}")

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


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

    threads = max(1, args.threads or int(os.getenv("AI_DOCS_THREADS", "5")))
    llm = from_env(concurrency=threads)
    cache_dir_name = args.cache_dir

    def _do_regen():
        print("[ai-docs watch] change detected — regenerating…")
        start = time.monotonic()
        _regen(args, llm)
        print(f"[ai-docs watch] regen done in {time.monotonic() - start:.1f}s")

    debouncer = _Debouncer(args.debounce, _do_regen)

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event):  # noqa: D401
            if event.is_directory:
                return
            path = Path(event.src_path).resolve()
            try:
                rel = path.relative_to(root)
            except ValueError:
                return
            parts = rel.parts
            if cache_dir_name in parts or ".git" in parts or "ai_docs_site" in parts:
                return
            if any(p.startswith(".") and p != "." for p in parts[:-1]):
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
