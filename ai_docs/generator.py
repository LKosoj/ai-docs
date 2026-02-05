import asyncio
import os
from pathlib import Path
from typing import Dict, List

from .generator_cache import (
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
from .generator_summarize import (
    summarize_changed_configs,
    summarize_changed_files,
    summarize_changed_modules,
    summarize_missing,
    summarize_missing_configs,
    summarize_missing_modules,
)


async def _generate_docs_async(
    files: List[Dict],
    output_root: Path,
    cache_dir: Path,
    llm,
    language: str,
    write_readme_flag: bool,
    write_mkdocs: bool,
    use_cache: bool = True,
    threads: int = 1,
    local_site: bool = False,
    force: bool = False,
) -> None:
    regen_raw = os.getenv("AI_DOCS_REGEN", "")
    force_sections = {item.strip().lower() for item in regen_raw.split(",") if item.strip()}
    if force_sections:
        print(f"[ai-docs] regen sections: {', '.join(sorted(force_sections))}")

    cache, llm_cache, index_data, prev_files = init_cache(cache_dir, use_cache)
    errors: List[str] = []

    file_map = build_file_map(files)
    added, modified, deleted, unchanged = diff_files(cache, file_map)
    print(f"[ai-docs] diff: added={len(added)} modified={len(modified)} deleted={len(deleted)} unchanged={len(unchanged)}")

    summaries_dir, module_summaries_dir, config_summaries_dir = ensure_summary_dirs(cache_dir)

    def save_cb() -> None:
        save_cache_snapshot(cache, file_map, index_data, llm_cache, use_cache)

    to_summarize = list({**added, **modified}.items())
    if to_summarize:
        print(f"[ai-docs] summarize: {len(to_summarize)} changed files (threads={threads})")
    await summarize_changed_files(to_summarize, summaries_dir, llm, llm_cache, threads, save_cb, errors)
    await summarize_changed_modules(to_summarize, module_summaries_dir, llm, llm_cache, threads, save_cb, errors)
    await summarize_changed_configs(to_summarize, config_summaries_dir, llm, llm_cache, threads, save_cb, errors)
    if to_summarize:
        save_cb()

    missing_summaries, missing_module_summaries, missing_config_summaries = carry_unchanged_summaries(
        unchanged, prev_files
    )
    if missing_summaries:
        print(f"[ai-docs] summarize: {len(missing_summaries)} missing summaries")
    await summarize_missing(missing_summaries, summaries_dir, llm, llm_cache, threads, save_cb, errors)
    if missing_module_summaries:
        print(f"[ai-docs] summarize modules: {len(missing_module_summaries)} missing module summaries")
    await summarize_missing_modules(missing_module_summaries, module_summaries_dir, llm, llm_cache, threads, save_cb, errors)
    if missing_config_summaries:
        print(f"[ai-docs] summarize configs: {len(missing_config_summaries)} missing config summaries")
    await summarize_missing_configs(missing_config_summaries, config_summaries_dir, llm, llm_cache, threads, save_cb, errors)
    if missing_summaries or missing_module_summaries or missing_config_summaries:
        save_cb()

    cleanup_orphan_summaries(file_map, summaries_dir, module_summaries_dir, config_summaries_dir)
    if deleted:
        print(f"[ai-docs] cleanup: removing {len(deleted)} deleted summaries")
        cleanup_deleted_summaries(deleted)

    input_budget = max(512, llm.context_limit - llm.max_tokens - 200)

    docs_dir = output_root / ".ai-docs"
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
        force_sections=force_sections or None,
    )

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
    save_cache_snapshot(cache, file_map, index_data, llm_cache, use_cache)

    if errors:
        print("[ai-docs] errors summary:")
        for item in errors:
            print(f"[ai-docs] error: {item}")


def generate_docs(
    files: List[Dict],
    output_root: Path,
    cache_dir: Path,
    llm,
    language: str,
    write_readme_flag: bool,
    write_mkdocs: bool,
    use_cache: bool = True,
    threads: int = 1,
    local_site: bool = False,
    force: bool = False,
) -> None:
    return asyncio.run(
        _generate_docs_async(
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
        )
    )


__all__ = [
    "generate_docs",
    "SECTION_TITLES",
    "DOMAIN_TITLES",
]
