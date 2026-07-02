"""`ai-docs pr-diff` — regenerate docs for files changed vs a base git ref.

Uses `git diff --name-status <base>...HEAD` to build changed/deleted masks,
scans the full current tree, and then runs the regular docs pipeline against
the full snapshot with regeneration limited to changed paths.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Set, Tuple

from .cli_common import (
    build_generation_config,
    close_llm,
    create_llm,
    resolve_local_site,
    resolve_output,
    resolve_threads,
)
from .generator import generate_docs
from .scanner import build_scan_scope, scan_source
from .utils import is_url


def _changed_file_masks(root: Path, base: str) -> Tuple[Set[str], Set[str]]:
    cmd = ["git", "-C", str(root), "diff", "--name-status", "-z", f"{base}...HEAD"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    tokens = [token for token in result.stdout.split("\0") if token]
    current_paths: Set[str] = set()
    deleted_paths: Set[str] = set()
    idx = 0
    while idx < len(tokens):
        status = tokens[idx]
        idx += 1
        if idx >= len(tokens):
            break
        code = status[:1]
        if code in {"R", "C"}:
            old_path = tokens[idx]
            new_path = tokens[idx + 1] if idx + 1 < len(tokens) else ""
            idx += 2
            if code == "R" and old_path:
                deleted_paths.add(old_path)
            if new_path:
                current_paths.add(new_path)
            continue
        path = tokens[idx]
        idx += 1
        if code == "D":
            deleted_paths.add(path)
        else:
            current_paths.add(path)
    return current_paths, deleted_paths


def run_prdiff(args: argparse.Namespace) -> int:
    if is_url(args.source):
        print("[ai-docs pr-diff] URL sources are not supported")
        return 2

    root = Path(args.source).expanduser().resolve()
    if not (root / ".git").exists():
        print(f"[ai-docs pr-diff] not a git repository: {root}")
        return 2

    try:
        changed, deleted = _changed_file_masks(root, args.base)
    except RuntimeError as exc:
        print(f"[ai-docs pr-diff] {exc}")
        return 2

    if not changed and not deleted:
        print(f"[ai-docs pr-diff] no changes vs {args.base}")
        return 0

    print(f"[ai-docs pr-diff] {len(changed)} changed file(s), {len(deleted)} deleted file(s) vs {args.base}:")
    for path in sorted(changed):
        print(f"  - {path}")
    for path in sorted(deleted):
        print(f"  - {path} (deleted)")

    include: Optional[Set[str]] = set(args.include) if args.include else None
    exclude: Optional[Set[str]] = set(args.exclude) if args.exclude else None
    threads = resolve_threads(args.threads)
    local_site = resolve_local_site(args.local_site)
    scan_result = scan_source(
        args.source,
        include=include,
        exclude=exclude,
        max_size=args.max_size,
        workers=threads,
    )
    scanned_paths = {item["path"] for item in scan_result.files}
    changed &= scanned_paths
    scan_scope = build_scan_scope(scan_result.root, include=include, exclude=exclude)
    deleted = {path for path in deleted if scan_scope.includes(path)}
    print(f"[ai-docs pr-diff] scan: {len(scan_result.files)} file(s) in current snapshot")
    if not scan_result.files and not deleted:
        print("[ai-docs pr-diff] nothing to regenerate")
        return 0
    if not changed and not deleted:
        print("[ai-docs pr-diff] changed files are outside the scan scope")
        return 0

    generation_config = build_generation_config(scan_result.root)
    output_root = resolve_output(args.source, args.output, scan_result.repo_name)
    output_root.mkdir(parents=True, exist_ok=True)
    llm = create_llm(threads)
    try:
        generate_docs(
            files=scan_result.files,
            output_root=output_root,
            cache_dir=output_root / args.cache_dir,
            llm=llm,
            language=args.language,
            write_readme_flag=args.readme,
            write_mkdocs=args.mkdocs,
            use_cache=not args.no_cache,
            threads=threads,
            local_site=local_site,
            force=False,
            changed_paths=changed,
            deleted_paths=deleted,
            generation_config=generation_config,
        )
    finally:
        close_llm(llm)
        if is_url(args.source):
            shutil.rmtree(scan_result.root, ignore_errors=True)
    return 0
