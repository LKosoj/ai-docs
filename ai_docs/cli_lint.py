"""`ai-docs lint` — detect files whose content changed since last docs generation.

Exits with code 0 if nothing stale, 1 if stale files exist, 2 on configuration errors.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Set

from .cache import CacheManager
from .generator_cache import build_file_map
from .scanner import scan_source
from .utils import is_url


def _collect_stale(cache_dir: Path, files: list) -> List[str]:
    cache = CacheManager(cache_dir)
    file_map = build_file_map(files)
    added, modified, deleted, _ = cache.diff_files(file_map)
    stale = sorted(list(added.keys()) + list(modified.keys()) + list(deleted.keys()))
    return stale


def run_lint(args: argparse.Namespace) -> int:
    if is_url(args.source):
        print("[ai-docs lint] URL sources are not supported")
        return 2

    include: Optional[Set[str]] = set(args.include) if args.include else None
    exclude: Optional[Set[str]] = set(args.exclude) if args.exclude else None

    scan_result = scan_source(
        args.source,
        include=include,
        exclude=exclude,
        max_size=args.max_size,
        workers=max(1, args.threads or 1),
    )
    cache_dir = scan_result.root / args.cache_dir
    if not (cache_dir / "index.json").exists():
        print(
            f"[ai-docs lint] index not found: {cache_dir / 'index.json'}. "
            "Run `ai-docs gen` first to build a baseline.",
        )
        return 2

    stale = _collect_stale(cache_dir, scan_result.files)
    if not stale:
        print("[ai-docs lint] docs up-to-date")
        return 0

    if not args.quiet:
        print(f"[ai-docs lint] {len(stale)} file(s) out of sync with generated docs:")
        for path in stale:
            print(f"  - {path}")
    else:
        print(f"[ai-docs lint] {len(stale)} stale file(s)")
    return 1
