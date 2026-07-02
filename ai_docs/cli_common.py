import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from .config import parse_bool_env, parse_int_env
from .generation_config import GenerationConfig, parse_section_list
from .llm import from_env
from .prompts import PromptStore, load_prompt_overrides
from .scanner import ScanResult, scan_source
from .site_config import load_source_url


@dataclass
class RunContext:
    scan_result: ScanResult
    include: Optional[Set[str]]
    exclude: Optional[Set[str]]
    threads: int
    local_site: bool
    output_root: Path
    generation_config: GenerationConfig
    llm: object


def close_llm(llm) -> None:
    aclose = getattr(llm, "aclose", None)
    if aclose is not None:
        asyncio.run(aclose())


def resolve_threads(arg_threads: Optional[int]) -> int:
    env_threads = parse_int_env("AI_DOCS_THREADS", 5)
    return max(1, arg_threads if arg_threads is not None else env_threads)


def resolve_local_site(flag: bool) -> bool:
    return flag or parse_bool_env("AI_DOCS_LOCAL_SITE", False)


def resolve_output(source: str, output: Optional[str], repo_name: str) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    source_path = Path(source).expanduser().resolve()
    if source_path.exists():
        return source_path
    return Path("output") / repo_name


def create_llm(threads: int):
    return from_env(concurrency=threads)


def build_generation_config(
    root: Path,
    regen_arg: Optional[str] = None,
    announce: bool = False,
) -> GenerationConfig:
    prompt_overrides = load_prompt_overrides(root)
    if announce and prompt_overrides:
        print(f"[ai-docs] custom prompts: {sorted(prompt_overrides.keys())}")

    source_url = load_source_url(root)
    if announce and source_url:
        print(f"[ai-docs] source_url: {source_url}")

    regen_raw = regen_arg if regen_arg is not None else os.getenv("AI_DOCS_REGEN", "")
    return GenerationConfig(
        prompt_store=PromptStore(prompt_overrides),
        source_url=source_url,
        force_sections=parse_section_list(regen_raw),
        regen_all_threshold=parse_int_env("AI_DOCS_REGEN_ALL_THRESHOLD", 50),
    )


def prepare_run_context(
    args,
    regen_arg: Optional[str] = None,
    announce_config: bool = False,
) -> RunContext:
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
    generation_config = build_generation_config(
        scan_result.root,
        regen_arg=regen_arg,
        announce=announce_config,
    )
    output_root = resolve_output(args.source, args.output, scan_result.repo_name)
    output_root.mkdir(parents=True, exist_ok=True)
    llm = create_llm(threads)

    return RunContext(
        scan_result=scan_result,
        include=include,
        exclude=exclude,
        threads=threads,
        local_site=local_site,
        output_root=output_root,
        generation_config=generation_config,
        llm=llm,
    )
