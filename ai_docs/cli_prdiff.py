"""`ai-docs pr-diff` — regenerate docs for files changed vs a base git ref.

Uses `git diff --name-only <base>...HEAD` to pick changed files, narrows the
scan to those paths, and then runs the regular docs pipeline.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Set

from .generator import generate_docs
from .llm import from_env
from .prompts import configure as configure_prompts, load_prompt_overrides
from .scanner import scan_source
from .site_config import configure_source_url, load_source_url
from .utils import is_url


def _changed_files(root: Path, base: str) -> List[str]:
    cmd = ["git", "-C", str(root), "diff", "--name-only", f"{base}...HEAD"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def run_prdiff(args: argparse.Namespace) -> int:
    if is_url(args.source):
        print("[ai-docs pr-diff] URL sources are not supported")
        return 2

    root = Path(args.source).expanduser().resolve()
    if not (root / ".git").exists():
        print(f"[ai-docs pr-diff] not a git repository: {root}")
        return 2

    try:
        changed = _changed_files(root, args.base)
    except RuntimeError as exc:
        print(f"[ai-docs pr-diff] {exc}")
        return 2

    if not changed:
        print(f"[ai-docs pr-diff] no changes vs {args.base}")
        return 0

    print(f"[ai-docs pr-diff] {len(changed)} changed file(s) vs {args.base}:")
    for path in changed:
        print(f"  - {path}")

    include_set = set(args.include) if args.include else set()
    include_set.update(changed)

    include: Optional[Set[str]] = include_set
    exclude: Optional[Set[str]] = set(args.exclude) if args.exclude else None
    env_local_site = os.getenv("AI_DOCS_LOCAL_SITE", "false").strip().lower() in {"1", "true", "yes", "y"}
    threads = max(1, args.threads or int(os.getenv("AI_DOCS_THREADS", "5")))
    local_site = args.local_site or env_local_site

    scan_result = scan_source(
        args.source,
        include=include,
        exclude=exclude,
        max_size=args.max_size,
        workers=threads,
    )
    print(f"[ai-docs pr-diff] scan: {len(scan_result.files)} file(s) matched include-filter")
    if not scan_result.files:
        print("[ai-docs pr-diff] nothing to regenerate")
        return 0

    prompt_overrides = load_prompt_overrides(scan_result.root)
    configure_prompts(prompt_overrides)
    configure_source_url(load_source_url(scan_result.root))

    output_root = Path(args.output).expanduser().resolve() if args.output else scan_result.root
    output_root.mkdir(parents=True, exist_ok=True)

    llm = from_env(concurrency=threads)
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
    )

    if is_url(args.source):
        shutil.rmtree(scan_result.root, ignore_errors=True)
    return 0
