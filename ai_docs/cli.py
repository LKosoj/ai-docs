import argparse
import os
from pathlib import Path
from typing import Optional, Set

import shutil

from .generator import generate_docs
from .llm import from_env
from .scanner import scan_source
from .utils import is_url
from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate README + MkDocs documentation for a code/config repository.")
    parser.add_argument("--source", required=True, help="Path to local folder or git URL")
    parser.add_argument("--output", help="Output root directory. Defaults to source for local paths, or ./output/<repo> for URLs")
    parser.add_argument("--readme", action="store_true", help="Generate README.md")
    parser.add_argument("--mkdocs", action="store_true", help="Generate MkDocs docs site")
    parser.add_argument("--language", default="ru", help="Language for generated docs (ru|en)")
    parser.add_argument("--include", nargs="*", help="Include patterns (glob)")
    parser.add_argument("--exclude", nargs="*", help="Exclude patterns (glob)")
    parser.add_argument("--max-size", type=int, default=200_000, help="Max file size in bytes")
    parser.add_argument("--cache-dir", default=".ai_docs_cache", help="Cache directory")
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM cache")
    parser.add_argument("--threads", type=int, default=None, help="Number of parallel LLM workers")
    parser.add_argument("--local-site", action="store_true", help="Generate MkDocs config for local run")
    parser.add_argument("--force", action="store_true", help="Overwrite README.md if it already exists")
    parser.add_argument(
        "--regen",
        help="Comma-separated list of sections to regenerate (e.g. architecture,configs,modules,index,changes)",
    )
    return parser.parse_args()


def resolve_output(source: str, output: Optional[str], repo_name: str) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    source_path = Path(source).expanduser().resolve()
    if source_path.exists():
        return source_path
    return Path("output") / repo_name


def main() -> None:
    load_dotenv()
    args = parse_args()
    if not args.readme and not args.mkdocs and not args.regen:
        print(
            "[ai-docs] подсказка: разделы не перегенерируются, если файл уже есть. "
            "Используйте --regen architecture,configs,changes или --regen all."
        )
    include: Optional[Set[str]] = set(args.include) if args.include else None
    exclude: Optional[Set[str]] = set(args.exclude) if args.exclude else None

    scan_result = scan_source(args.source, include=include, exclude=exclude, max_size=args.max_size)
    root = scan_result.root
    repo_name = scan_result.repo_name
    print(f"[ai-docs] scan complete: {len(scan_result.files)} files")

    output_root = resolve_output(args.source, args.output, repo_name)
    output_root.mkdir(parents=True, exist_ok=True)

    llm = from_env()
    print(f"[ai-docs] llm: model={llm.model} context={llm.context_limit} max_tokens={llm.max_tokens}")

    env_threads = int(os.getenv("AI_DOCS_THREADS", "1"))
    env_local_site = os.getenv("AI_DOCS_LOCAL_SITE", "false").strip().lower() in {"1", "true", "yes", "y"}
    threads = args.threads if args.threads is not None else env_threads
    local_site = args.local_site or env_local_site

    print(f"[ai-docs] generate: readme={args.readme or not args.mkdocs} mkdocs={args.mkdocs or not args.readme}")
    if args.regen:
        os.environ["AI_DOCS_REGEN"] = args.regen
    generate_docs(
        files=scan_result.files,
        output_root=output_root,
        cache_dir=output_root / args.cache_dir,
        llm=llm,
        language=args.language,
        write_readme=(args.readme or not args.mkdocs),
        write_mkdocs=(args.mkdocs or not args.readme),
        use_cache=not args.no_cache,
        threads=max(1, threads),
        local_site=local_site,
        force=args.force,
    )

    if is_url(args.source):
        shutil.rmtree(scan_result.root, ignore_errors=True)


if __name__ == "__main__":
    main()
