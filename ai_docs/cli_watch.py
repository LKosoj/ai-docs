"""`ai-docs watch` — watch source tree, regenerate docs on change with debouncing.

Uses `watchdog` (optional dependency). Pattern:
  1. Scan once at startup, persist baseline.
  2. On any fs change under --source, restart a debounce timer.
  3. When the timer fires, run the same pipeline as `ai-docs gen`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Optional, Set

from .config import parse_bool_env, parse_int_env
from .generation_config import GenerationConfig, parse_section_list
from .generator import generate_docs
from .llm import from_env
from .prompts import PromptStore, load_prompt_overrides
from .scanner import scan_source
from .site_config import load_source_url
from .utils import is_url


def _close_llm(llm) -> None:
    aclose = getattr(llm, "aclose", None)
    if aclose is not None:
        asyncio.run(aclose())


def _regen(args: argparse.Namespace) -> None:
    include: Optional[Set[str]] = set(args.include) if args.include else None
    exclude: Optional[Set[str]] = set(args.exclude) if args.exclude else None
    threads = max(1, args.threads or parse_int_env("AI_DOCS_THREADS", 5))
    env_local_site = parse_bool_env("AI_DOCS_LOCAL_SITE", False)
    local_site = args.local_site or env_local_site

    scan_result = scan_source(
        args.source,
        include=include,
        exclude=exclude,
        max_size=args.max_size,
        workers=threads,
    )
    prompt_overrides = load_prompt_overrides(scan_result.root)
    source_url = load_source_url(scan_result.root)
    generation_config = GenerationConfig(
        prompt_store=PromptStore(prompt_overrides),
        source_url=source_url,
        force_sections=parse_section_list(os.getenv("AI_DOCS_REGEN", "")),
        regen_all_threshold=parse_int_env("AI_DOCS_REGEN_ALL_THRESHOLD", 50),
    )

    output_root = Path(args.output).expanduser().resolve() if args.output else scan_result.root
    output_root.mkdir(parents=True, exist_ok=True)

    llm = from_env(concurrency=threads)
    try:
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
            generation_config=generation_config,
        )
    finally:
        _close_llm(llm)
        if is_url(args.source):
            shutil.rmtree(scan_result.root, ignore_errors=True)


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
                print(f"[ai-docs watch] regeneration failed: {exc}")
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

    cache_dir_name = args.cache_dir

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
