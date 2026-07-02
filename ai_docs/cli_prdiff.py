"""`ai-docs pr-diff` — regenerate docs for files changed vs a base git ref.

Uses `git diff --name-status <base>...HEAD` to build changed/deleted masks,
scans the full current tree, and then runs the regular docs pipeline against
the full snapshot with regeneration limited to changed paths.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Set, Tuple

from .config import parse_bool_env, parse_int_env
from .generation_config import GenerationConfig, parse_section_list
from .generator import generate_docs
from .llm import from_env
from .prompts import PromptStore, load_prompt_overrides
from .scanner import path_in_scan_scope, scan_source
from .site_config import load_source_url
from .utils import is_url


def _close_llm(llm) -> None:
    aclose = getattr(llm, "aclose", None)
    if aclose is not None:
        asyncio.run(aclose())


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
    env_local_site = parse_bool_env("AI_DOCS_LOCAL_SITE", False)
    threads = max(1, args.threads or parse_int_env("AI_DOCS_THREADS", 5))
    local_site = args.local_site or env_local_site

    scan_result = scan_source(
        args.source,
        include=include,
        exclude=exclude,
        max_size=args.max_size,
        workers=threads,
    )
    scanned_paths = {item["path"] for item in scan_result.files}
    changed &= scanned_paths
    deleted = {
        path
        for path in deleted
        if path_in_scan_scope(scan_result.root, path, include=include, exclude=exclude)
    }
    print(f"[ai-docs pr-diff] scan: {len(scan_result.files)} file(s) in current snapshot")
    if not scan_result.files and not deleted:
        print("[ai-docs pr-diff] nothing to regenerate")
        return 0
    if not changed and not deleted:
        print("[ai-docs pr-diff] changed files are outside the scan scope")
        return 0

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
        _close_llm(llm)
        if is_url(args.source):
            shutil.rmtree(scan_result.root, ignore_errors=True)
    return 0
