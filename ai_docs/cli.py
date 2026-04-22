import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Set

import shutil

from .generator import generate_docs
from .llm import from_env
from .prompts import configure as configure_prompts, load_prompt_overrides
from .scanner import scan_source
from .site_config import configure_source_url, load_source_url
from .utils import is_url
from dotenv import load_dotenv


KNOWN_COMMANDS = {"gen", "lint", "watch", "pr-diff", "help"}


def _add_common_scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True, help="Path to local folder or git URL")
    parser.add_argument("--include", nargs="*", help="Include patterns (glob)")
    parser.add_argument("--exclude", nargs="*", help="Exclude patterns (glob)")
    parser.add_argument("--max-size", type=int, default=200_000, help="Max file size in bytes")
    parser.add_argument("--cache-dir", default=".ai_docs_cache", help="Cache directory")
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Number of parallel workers for scanning and LLM summarization",
    )


def _add_gen_args(parser: argparse.ArgumentParser) -> None:
    _add_common_scan_args(parser)
    parser.add_argument("--output", help="Output root directory. Defaults to source for local paths, or ./output/<repo> for URLs")
    parser.add_argument("--readme", action="store_true", help="Generate README.md")
    parser.add_argument("--mkdocs", action="store_true", help="Generate MkDocs docs site")
    parser.add_argument("--language", default="ru", help="Language for generated docs (ru|en)")
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM cache")
    parser.add_argument("--local-site", action="store_true", help="Generate MkDocs config for local run")
    parser.add_argument("--force", action="store_true", help="Overwrite README.md if it already exists")
    parser.add_argument(
        "--regen",
        help="Comma-separated list of sections to regenerate (e.g. architecture,configs,modules,index,changes)",
    )


def _add_lint_args(parser: argparse.ArgumentParser) -> None:
    _add_common_scan_args(parser)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress list of stale files (only exit code)",
    )


def _add_prdiff_args(parser: argparse.ArgumentParser) -> None:
    _add_common_scan_args(parser)
    parser.add_argument("--output", help="Output root directory")
    parser.add_argument("--base", default="main", help="Base git reference to diff against (default: main)")
    parser.add_argument("--language", default="ru", help="Language for generated docs (ru|en)")
    parser.add_argument("--mkdocs", action="store_true", help="Also update MkDocs site")
    parser.add_argument("--readme", action="store_true", help="Also update README.md")
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM cache")
    parser.add_argument("--local-site", action="store_true", help="Generate MkDocs config for local run")


def _add_watch_args(parser: argparse.ArgumentParser) -> None:
    _add_common_scan_args(parser)
    parser.add_argument("--output", help="Output root directory")
    parser.add_argument("--mkdocs", action="store_true", help="Also update MkDocs site on change")
    parser.add_argument("--readme", action="store_true", help="Also update README.md on change")
    parser.add_argument("--language", default="ru", help="Language for generated docs (ru|en)")
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM cache")
    parser.add_argument("--local-site", action="store_true", help="Generate MkDocs config for local run")
    parser.add_argument(
        "--debounce",
        type=float,
        default=2.0,
        help="Seconds to wait after last change before regenerating (default: 2.0)",
    )


def _normalize_argv(argv: Sequence[str]) -> List[str]:
    """Back-compat: if no subcommand given, implicit "gen"."""
    argv = list(argv)
    if not argv:
        return ["gen"]
    first = argv[0]
    if first.startswith("-"):
        return ["gen", *argv]
    if first in KNOWN_COMMANDS:
        return argv
    return ["gen", *argv]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-docs",
        description="Generate README + MkDocs documentation for a code/config repository.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen", help="Generate (or refresh) documentation")
    _add_gen_args(gen)

    lint = sub.add_parser("lint", help="Detect stale docs (files changed without doc regen)")
    _add_lint_args(lint)

    watch = sub.add_parser("watch", help="Watch source tree and regenerate docs on change")
    _add_watch_args(watch)

    prdiff = sub.add_parser("pr-diff", help="Regenerate docs only for files changed vs base branch")
    _add_prdiff_args(prdiff)

    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    raw = list(argv) if argv is not None else sys.argv[1:]
    normalized = _normalize_argv(raw)
    return _build_parser().parse_args(normalized)


def resolve_output(source: str, output: Optional[str], repo_name: str) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    source_path = Path(source).expanduser().resolve()
    if source_path.exists():
        return source_path
    return Path("output") / repo_name


def _resolve_threads(arg_threads: Optional[int]) -> int:
    env_threads = int(os.getenv("AI_DOCS_THREADS", "5"))
    return max(1, arg_threads if arg_threads is not None else env_threads)


def _run_gen(args: argparse.Namespace) -> int:
    if not args.readme and not args.mkdocs and not args.regen:
        print(
            "[ai-docs] подсказка: разделы не перегенерируются, если файл уже есть. "
            "Используйте --regen architecture,configs,changes или --regen all."
        )
    include: Optional[Set[str]] = set(args.include) if args.include else None
    exclude: Optional[Set[str]] = set(args.exclude) if args.exclude else None
    env_local_site = os.getenv("AI_DOCS_LOCAL_SITE", "false").strip().lower() in {"1", "true", "yes", "y"}
    threads = _resolve_threads(args.threads)
    local_site = args.local_site or env_local_site

    scan_result = scan_source(
        args.source,
        include=include,
        exclude=exclude,
        max_size=args.max_size,
        workers=threads,
    )
    root = scan_result.root
    repo_name = scan_result.repo_name
    print(f"[ai-docs] scan complete: {len(scan_result.files)} files")

    prompt_overrides = load_prompt_overrides(root)
    configure_prompts(prompt_overrides)
    if prompt_overrides:
        print(f"[ai-docs] custom prompts: {sorted(prompt_overrides.keys())}")

    source_url = load_source_url(root)
    configure_source_url(source_url)
    if source_url:
        print(f"[ai-docs] source_url: {source_url}")

    output_root = resolve_output(args.source, args.output, repo_name)
    output_root.mkdir(parents=True, exist_ok=True)

    llm = from_env(concurrency=threads)
    print(
        f"[ai-docs] llm: model={llm.model} context={llm.context_limit} "
        f"max_tokens={llm.max_tokens} concurrency={llm.concurrency}"
    )

    print(f"[ai-docs] generate: readme={args.readme or not args.mkdocs} mkdocs={args.mkdocs or not args.readme}")
    if args.regen:
        os.environ["AI_DOCS_REGEN"] = args.regen
    generate_docs(
        files=scan_result.files,
        output_root=output_root,
        cache_dir=output_root / args.cache_dir,
        llm=llm,
        language=args.language,
        write_readme_flag=(args.readme or not args.mkdocs),
        write_mkdocs=(args.mkdocs or not args.readme),
        use_cache=not args.no_cache,
        threads=threads,
        local_site=local_site,
        force=args.force,
    )

    if is_url(args.source):
        shutil.rmtree(scan_result.root, ignore_errors=True)
    return 0


def _run_lint(args: argparse.Namespace) -> int:
    from .cli_lint import run_lint
    return run_lint(args)


def _run_watch(args: argparse.Namespace) -> int:
    from .cli_watch import run_watch
    return run_watch(args)


def _run_prdiff(args: argparse.Namespace) -> int:
    from .cli_prdiff import run_prdiff
    return run_prdiff(args)


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    handlers = {
        "gen": _run_gen,
        "lint": _run_lint,
        "watch": _run_watch,
        "pr-diff": _run_prdiff,
    }
    handler = handlers[args.command]
    rc = handler(args)
    if rc is None:
        rc = 0
    return rc


if __name__ == "__main__":
    sys.exit(main())
