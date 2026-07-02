import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set

from .generation_config import GenerationConfig
from .generator_cache import (
    build_masked_snapshot,
    build_file_map,
    carry_unchanged_summaries,
    cleanup_deleted_summaries,
    cleanup_orphan_summaries,
    diff_files,
    ensure_summary_dirs,
    init_cache,
    save_cache_snapshot,
)
from .generator_output import build_mkdocs, write_docs, write_readme
from .generator_sections import build_sections, generate_readme
from .generator_shared import DOMAIN_TITLES, SECTION_TITLES
from .generator_summarize import summarize_entries
from .llm import LLMProtocol
from .prompts import PromptStore


class GenerationError(RuntimeError):
    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        message = "Documentation generation failed:\n" + "\n".join(f"- {item}" for item in self.errors)
        super().__init__(message)


def _raise_if_summarization_failed(errors: List[str]) -> None:
    if not errors:
        return
    print("[ai-docs] errors summary:")
    for item in errors:
        print(f"[ai-docs] error: {item}")
    raise GenerationError(errors)


def _resolve_generation_config(
    generation_config: Optional[GenerationConfig],
    prompt_store: Optional[PromptStore],
    source_url: Optional[str],
    force_sections: Optional[Set[str]],
    regen_all_threshold: Optional[int],
) -> GenerationConfig:
    base = generation_config or GenerationConfig()
    return GenerationConfig(
        prompt_store=prompt_store or base.prompt_store,
        source_url=source_url if source_url is not None else base.source_url,
        force_sections=set(force_sections if force_sections is not None else base.force_sections),
        regen_all_threshold=regen_all_threshold
        if regen_all_threshold is not None
        else base.regen_all_threshold,
    )


async def generate_docs_async(
    files: List[Dict],
    output_root: Path,
    cache_dir: Path,
    llm: LLMProtocol,
    language: str,
    write_readme_flag: bool,
    write_mkdocs: bool,
    use_cache: bool = True,
    threads: int = 1,
    local_site: bool = False,
    force: bool = False,
    changed_paths: Optional[Set[str]] = None,
    deleted_paths: Optional[Set[str]] = None,
    generation_config: Optional[GenerationConfig] = None,
    prompt_store: Optional[PromptStore] = None,
    source_url: Optional[str] = None,
    force_sections: Optional[Set[str]] = None,
    regen_all_threshold: Optional[int] = None,
) -> None:
    config = _resolve_generation_config(
        generation_config,
        prompt_store,
        source_url,
        force_sections,
        regen_all_threshold,
    )
    if config.force_sections:
        print(f"[ai-docs] regen sections: {', '.join(sorted(config.force_sections))}")

    cache, llm_cache, index_data, prev_files = init_cache(cache_dir, use_cache)
    errors: List[str] = []

    file_map = build_file_map(files)
    added_all, modified_all, deleted_all, unchanged_all = diff_files(cache, file_map)
    mask_enabled = changed_paths is not None or deleted_paths is not None
    changed_mask = set(changed_paths or set())
    deleted_mask = set(deleted_paths or set())
    if mask_enabled:
        added = {path: meta for path, meta in added_all.items() if path in changed_mask}
        modified = {path: meta for path, meta in modified_all.items() if path in changed_mask}
        deleted = {path: meta for path, meta in deleted_all.items() if path in deleted_mask}
        unchanged = {
            path: meta
            for path, meta in file_map.items()
            if path in prev_files and path not in changed_mask and path not in deleted_mask
        }
    else:
        added, modified, deleted, unchanged = added_all, modified_all, deleted_all, unchanged_all
    print(f"[ai-docs] diff: added={len(added)} modified={len(modified)} deleted={len(deleted)} unchanged={len(unchanged)}")

    summaries_dir, module_summaries_dir, config_summaries_dir = ensure_summary_dirs(cache_dir)

    def save_cb() -> None:
        snapshot_files = build_masked_snapshot(file_map, prev_files, changed_paths, deleted_paths)
        save_cache_snapshot(cache, file_map, index_data, llm_cache, use_cache, snapshot_files=snapshot_files)

    to_summarize = list({**added, **modified}.items())
    if to_summarize:
        print(f"[ai-docs] summarize: {len(to_summarize)} changed files (threads={threads})")
    await summarize_entries(
        to_summarize,
        summaries_dir,
        module_summaries_dir,
        config_summaries_dir,
        llm,
        llm_cache,
        threads,
        save_cb,
        errors,
        label="summarize progress",
        prompt_store=config.prompt_store,
    )
    _raise_if_summarization_failed(errors)
    if to_summarize:
        save_cb()

    missing_entries = carry_unchanged_summaries(unchanged, prev_files)
    if missing_entries:
        print(f"[ai-docs] summarize: {len(missing_entries)} missing summaries")
    await summarize_entries(
        missing_entries,
        summaries_dir,
        module_summaries_dir,
        config_summaries_dir,
        llm,
        llm_cache,
        threads,
        save_cb,
        errors,
        label="summarize missing progress",
        prompt_store=config.prompt_store,
    )
    _raise_if_summarization_failed(errors)
    if missing_entries:
        save_cb()

    cleanup_orphan_summaries(file_map, summaries_dir, module_summaries_dir, config_summaries_dir)
    if deleted:
        print(f"[ai-docs] cleanup: removing {len(deleted)} deleted summaries")
        cleanup_deleted_summaries(deleted)

    input_budget = max(512, llm.context_limit - llm.max_tokens - 200)

    docs_dir = output_root / ".ai-docs"
    try:
        (
            docs_files,
            module_pages,
            config_pages,
            module_nav_paths,
            config_nav_paths,
            configs_written,
            regenerated_sections,
            overview_context,
        ) = await build_sections(
            file_map,
            added,
            modified,
            deleted,
            docs_dir,
            llm,
            llm_cache,
            language,
            threads,
            input_budget,
            force_sections=config.force_sections or None,
            source_url=config.source_url,
            regen_all_threshold=config.regen_all_threshold,
        )
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError([f"sections: {exc}"]) from exc

    has_changes = bool(added or modified or deleted)
    write_docs(output_root, docs_dir, docs_files, file_map, module_pages, config_pages, has_changes)

    if write_readme_flag:
        print("[ai-docs] write README")
        readme = await generate_readme(llm, llm_cache, output_root.name, overview_context, language)
        write_readme(output_root, readme, force)

    build_mkdocs(
        output_root,
        module_nav_paths,
        config_nav_paths,
        configs_written,
        write_mkdocs,
        local_site,
    )

    index_data["sections"] = {"regenerated": regenerated_sections}
    save_cb()


_generate_docs_async = generate_docs_async


def generate_docs(
    files: List[Dict],
    output_root: Path,
    cache_dir: Path,
    llm: LLMProtocol,
    language: str,
    write_readme_flag: bool,
    write_mkdocs: bool,
    use_cache: bool = True,
    threads: int = 1,
    local_site: bool = False,
    force: bool = False,
    changed_paths: Optional[Set[str]] = None,
    deleted_paths: Optional[Set[str]] = None,
    generation_config: Optional[GenerationConfig] = None,
    prompt_store: Optional[PromptStore] = None,
    source_url: Optional[str] = None,
    force_sections: Optional[Set[str]] = None,
    regen_all_threshold: Optional[int] = None,
) -> None:
    return asyncio.run(
        generate_docs_async(
            files=files,
            output_root=output_root,
            cache_dir=cache_dir,
            llm=llm,
            language=language,
            write_readme_flag=write_readme_flag,
            write_mkdocs=write_mkdocs,
            use_cache=use_cache,
            threads=threads,
            local_site=local_site,
            force=force,
            changed_paths=changed_paths,
            deleted_paths=deleted_paths,
            generation_config=generation_config,
            prompt_store=prompt_store,
            source_url=source_url,
            force_sections=force_sections,
            regen_all_threshold=regen_all_threshold,
        )
    )


__all__ = [
    "GenerationError",
    "generate_docs",
    "generate_docs_async",
    "SECTION_TITLES",
    "DOMAIN_TITLES",
]
