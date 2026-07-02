import argparse
import io
import shutil
import sys
from contextlib import redirect_stdout
from typing import List, Optional, Sequence

from dotenv import load_dotenv

from .cache import CacheError
from .cli_common import close_llm, prepare_run_context
from .config import ConfigError
from .generator import GenerationError, generate_docs
from .logging_utils import configure_logging
from .utils import is_url


KNOWN_COMMANDS = {"gen", "lint", "watch", "pr-diff", "help"}


def _add_common_scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True, help="Path to local folder or git URL")
    parser.add_argument("--include", nargs="*", help="Include patterns (glob)")
    parser.add_argument("--exclude", nargs="*", help="Exclude patterns (glob)")
    parser.add_argument("--max-size", type=int, default=200_000, help="Max file size in bytes")
    parser.add_argument("--cache-dir", default=".ai_docs_cache", help="Cache directory")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational logs where supported")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose diagnostic logs")
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
    if first == "help":
        if len(argv) == 1:
            return ["--help"]
        return [argv[1], "--help", *argv[2:]]
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


def _run_gen(args: argparse.Namespace) -> int:
    if not args.readme and not args.mkdocs and not args.regen:
        print(
            "[ai-docs] подсказка: разделы не перегенерируются, если файл уже есть. "
            "Используйте --regen architecture,configs,changes или --regen all."
        )
    context = prepare_run_context(args, regen_arg=args.regen, announce_config=True)
    print(f"[ai-docs] scan complete: {len(context.scan_result.files)} files")

    llm = context.llm
    print(
        f"[ai-docs] llm: model={llm.model} context={llm.context_limit} "
        f"max_tokens={llm.max_tokens} concurrency={llm.concurrency}"
    )

    try:
        print(f"[ai-docs] generate: readme={args.readme or not args.mkdocs} mkdocs={args.mkdocs or not args.readme}")
        generate_docs(
            files=context.scan_result.files,
            output_root=context.output_root,
            cache_dir=context.output_root / args.cache_dir,
            llm=llm,
            language=args.language,
            write_readme_flag=(args.readme or not args.mkdocs),
            write_mkdocs=(args.mkdocs or not args.readme),
            use_cache=not args.no_cache,
            threads=context.threads,
            local_site=context.local_site,
            force=args.force,
            generation_config=context.generation_config,
        )
    finally:
        close_llm(llm)
        if is_url(args.source):
            shutil.rmtree(context.scan_result.root, ignore_errors=True)
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


def _flush_captured_stdout(captured_stdout: Optional[io.StringIO]) -> None:
    if captured_stdout is None:
        return
    output = captured_stdout.getvalue().strip()
    if output:
        print(output, file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_dotenv()
    captured_stdout: Optional[io.StringIO] = None
    try:
        args = parse_args(argv)
        configure_logging(verbose=args.verbose, quiet=args.quiet)
        handlers = {
            "gen": _run_gen,
            "lint": _run_lint,
            "watch": _run_watch,
            "pr-diff": _run_prdiff,
        }
        handler = handlers[args.command]
        if args.quiet and args.command != "lint":
            captured_stdout = io.StringIO()
            with redirect_stdout(captured_stdout):
                rc = handler(args)
        else:
            rc = handler(args)
        if rc is None:
            rc = 0
        if args.quiet and args.command != "lint" and rc != 0:
            _flush_captured_stdout(captured_stdout)
        return rc
    except GenerationError as exc:
        _flush_captured_stdout(captured_stdout)
        print(f"[ai-docs] generation failed: {exc}", file=sys.stderr)
        return 1
    except (ConfigError, CacheError) as exc:
        _flush_captured_stdout(captured_stdout)
        print(f"[ai-docs] configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
