import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .changes import format_changes_md
from .generator_shared import (
    SECTION_TITLES,
    DOMAIN_TITLES,
    collect_dependencies,
    collect_test_info,
    render_project_configs_index,
    render_testing_section,
    strip_duplicate_heading,
    is_test_path,
)
from .tokenizer import count_tokens, chunk_text
from .utils import read_text_file


async def generate_section(llm, llm_cache: Dict[str, str], title: str, context: str, language: str) -> str:
    prompt = (
        "Ты опытный технический писатель. Сгенерируй раздел документации в Markdown. "
        f"Язык: {language}. Раздел: {title}. "
        "Используй предоставленный контекст. Избегай воды, дай практические детали."
    )
    if title.lower() == "архитектура":
        prompt += (
            " В начале раздела обязательно вставь Mermaid-диаграмму архитектуры. "
            "Используй блок:\n```mermaid\n...\n```.\n"
            "Схема должна отражать основные компоненты и потоки данных проекта. "
            "Используй `-->` для связей. Запрещено использовать `>`. "
            "Внутри блока Mermaid запрещены круглые скобки `(` и `)` в любых строках. "
            "Для подписей используй квадратные скобки."
        )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": context},
    ]
    content = (await llm.chat(messages, cache=llm_cache)).strip()
    return strip_duplicate_heading(content, title)


async def generate_readme(llm, llm_cache: Dict[str, str], project_name: str, overview_context: str, language: str) -> str:
    prompt = (
        "Сформируй README.md для проекта. "
        "Структура: Обзор, Быстрый старт, Архитектура (кратко), Ссылки на docs. "
        "Текст должен быть кратким и полезным. Язык: " + language
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": overview_context},
    ]
    return (await llm.chat(messages, cache=llm_cache)).strip()


def truncate_context(context: str, model: str, max_tokens: int) -> str:
    if count_tokens(context, model) <= max_tokens:
        return context
    chunks = chunk_text(context, model=model, max_tokens=max_tokens)
    return chunks[0]


async def summarize_chunk(
    llm,
    llm_cache: Dict[str, str],
    chunk: str,
    language: str,
    focus: str = "",
) -> str:
    prompt = (
        "Сожми следующий контекст до краткого, но информативного конспекта. "
        "Сохрани ключевые сущности, связи, архитектурные решения и важные названия. "
        "Не добавляй фактов от себя. "
    )
    if focus:
        prompt += f"Фокус: {focus}. "
    prompt += "Язык: " + language
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": chunk},
    ]
    return (await llm.chat(messages, cache=llm_cache)).strip()


async def build_hierarchical_context(
    llm,
    llm_cache: Dict[str, str],
    texts: List[str],
    max_tokens: int,
    language: str,
    label: str,
    focus: str = "",
) -> str:
    items = [t.strip() for t in texts if t and t.strip()]
    if not items:
        return ""
    joined = "\n\n".join(items)
    if count_tokens(joined, llm.model) <= max_tokens:
        return joined

    current = items
    max_rounds = 6
    for round_idx in range(1, max_rounds + 1):
        joined = "\n\n".join(current)
        if count_tokens(joined, llm.model) <= max_tokens:
            return joined

        chunks = chunk_text(joined, model=llm.model, max_tokens=max_tokens)
        summaries: List[str] = []
        for idx, chunk in enumerate(chunks, 1):
            print(f"[ai-docs] summarize chunk {label}: {round_idx}.{idx}/{len(chunks)}")
            summary = await summarize_chunk(llm, llm_cache, chunk, language, focus)
            if summary:
                summaries.append(summary)

        if not summaries:
            return truncate_context(joined, llm.model, max_tokens)

        new_joined = "\n\n".join(summaries)
        if count_tokens(new_joined, llm.model) >= count_tokens(joined, llm.model) and len(summaries) == 1:
            return truncate_context(new_joined, llm.model, max_tokens)
        current = summaries

    return truncate_context("\n\n".join(current), llm.model, max_tokens)


async def build_sections(
    file_map: Dict[str, Dict],
    added: Dict[str, Dict],
    modified: Dict[str, Dict],
    deleted: Dict[str, Dict],
    docs_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    language: str,
    threads: int,
    input_budget: int,
    force_sections: Optional[Set[str]] = None,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], List[str], List[str], Dict[str, str], List[str], str]:
    force_sections = {item.strip().lower() for item in (force_sections or set()) if item.strip()}
    regen_all_threshold = int(os.getenv("AI_DOCS_REGEN_ALL_THRESHOLD", "50"))
    module_count = sum(
        1
        for path, meta in file_map.items()
        if meta.get("type") == "code" and not is_test_path(path)
    )
    if module_count and module_count < regen_all_threshold:
        force_sections.add("all")
        print(f"[ai-docs] regen all: module_count={module_count} threshold={regen_all_threshold}")
    force_all = "all" in force_sections or "*" in force_sections

    def is_forced(*tokens: str) -> bool:
        if force_all:
            return True
        for token in tokens:
            token_norm = token.strip().lower()
            if token_norm and token_norm in force_sections:
                return True
        return False

    changed_domains: Set[str] = set()
    for path, meta in {**added, **modified, **deleted}.items():
        changed_domains.update(meta.get("domains", []))

    domain_contexts: Dict[str, str] = {}
    for domain in DOMAIN_TITLES.keys():
        domain_files = [m for m in file_map.values() if domain in m.get("domains", [])]
        if not domain_files:
            continue
        summaries = []
        for m in domain_files:
            summary_path = m.get("summary_path")
            if summary_path:
                summaries.append(read_text_file(Path(summary_path)))
        if summaries:
            domain_contexts[domain] = await build_hierarchical_context(
                llm,
                llm_cache,
                summaries,
                input_budget,
                language,
                f"domain:{domain}",
                focus=DOMAIN_TITLES.get(domain, domain),
            )

    test_paths, test_commands = collect_test_info(file_map)

    all_summaries = [
        read_text_file(Path(m["summary_path"]))
        for m in file_map.values()
        if m.get("summary_path")
    ]

    docs_files: Dict[str, str] = {}
    overview_path = docs_dir / "overview.md"
    overview_forced = is_forced("overview", "section:overview", "overview.md")
    should_regen_overview = overview_forced or force_all or not overview_path.exists()
    if should_regen_overview:
        print("[ai-docs] regen section: overview")
        overview_context = await build_hierarchical_context(
            llm,
            llm_cache,
            all_summaries,
            input_budget,
            language,
            "overview",
            focus="Обзор проекта",
        )
        docs_files["overview.md"] = f"# Обзор проекта\n\n{overview_context}\n"
    else:
        print("[ai-docs] skip section: overview (cached)")
        overview_text = read_text_file(overview_path)
        overview_lines = overview_text.splitlines()
        if overview_lines and overview_lines[0].lstrip().startswith("#"):
            overview_context = "\n".join(overview_lines[1:]).lstrip()
        else:
            overview_context = overview_text.strip()
        docs_files["overview.md"] = overview_text if overview_text.endswith("\n") else overview_text + "\n"

    section_contexts: Dict[str, str] = {}

    async def get_section_context(section_key: str, section_title: str) -> str:
        if section_key not in section_contexts:
            section_contexts[section_key] = await build_hierarchical_context(
                llm,
                llm_cache,
                all_summaries,
                input_budget,
                language,
                f"section:{section_key}",
                focus=section_title,
            )
        return section_contexts[section_key]

    regenerated_sections: List[str] = []
    module_pages: Dict[str, str] = {}
    configs_written: Dict[str, str] = {}
    section_tasks: List[asyncio.Task] = []
    section_sem = asyncio.Semaphore(min(threads, 4) if threads > 1 else 1)

    def submit_section(out_path: str, title: str, context: str) -> None:
        async def run_section() -> None:
            print(f"[ai-docs] regen section: {title}")
            async with section_sem:
                content = await generate_section(llm, llm_cache, title, context, language)
            docs_files[out_path] = f"# {title}\n\n{content}\n"
            regenerated_sections.append(title)

        section_tasks.append(asyncio.create_task(run_section()))

    for key, title in SECTION_TITLES.items():
        section_path = docs_dir / f"{key}.md"
        forced = is_forced(key, title, f"section:{key}", f"section:{title}")
        if forced or not section_path.exists():
            if key == "testing":
                print(f"[ai-docs] regen section: {title}")
                docs_files["testing.md"] = f"# {title}\n\n{render_testing_section(test_paths, test_commands)}\n"
                regenerated_sections.append(title)
                continue
            submit_section(f"{key}.md", title, await get_section_context(key, title))

    for domain, title in DOMAIN_TITLES.items():
        if domain not in domain_contexts:
            continue
        filename = f"{domain}.md"
        domain_path = docs_dir / "configs" / filename
        forced = is_forced(domain, title, f"domain:{domain}", "domains", "configs")
        if forced or not domain_path.exists():
            print(f"[ai-docs] regen section: {title}")
            submit_section(f"configs/{filename}", title, domain_contexts[domain])
        configs_written[domain] = filename

    index_title = "Документация проекта"
    index_path = docs_dir / "index.md"
    if is_forced("index", "docs", "documentation") or not index_path.exists():
        print(f"[ai-docs] regen section: {index_title}")
        submit_section("index.md", index_title, await get_section_context("index", index_title))

    module_summaries = []
    module_nav_paths: List[str] = []
    for path, meta in file_map.items():
        if is_test_path(path):
            continue
        summary_path = meta.get("module_summary_path")
        if not summary_path:
            continue
        module_rel = Path("modules") / Path(path)
        module_rel_str = module_rel.as_posix().replace(".", "__") + ".md"
        module_title = Path(path).with_suffix("").as_posix()
        summary = read_text_file(Path(summary_path))
        module_pages[module_rel_str] = f"# {module_title}\n\n{summary}\n"
        module_nav_paths.append(module_rel_str)
        module_summaries.append(summary)
    if module_summaries:
        modules_title = "Модули"
        sorted_modules = sorted(module_nav_paths)
        per_page = 100
        total = len(sorted_modules)
        pages = [sorted_modules[i : i + per_page] for i in range(0, total, per_page)]
        modules_index_path = docs_dir / "modules" / "index.md"
        if is_forced("modules") or not modules_index_path.exists():
            print(f"[ai-docs] regen section: {modules_title}")
            modules_context = await build_hierarchical_context(
                llm,
                llm_cache,
                module_summaries,
                input_budget,
                language,
                "modules",
                focus=modules_title,
            )
            intro = await generate_section(llm, llm_cache, modules_title, modules_context, language)
            for page_idx, page_items in enumerate(pages, start=1):
                toc_lines = "\n".join(
                    [
                        f"- [{Path(p).with_suffix('').as_posix()}]({Path(p).as_posix()[len('modules/'):] if p.startswith('modules/') else p})"
                        for p in page_items
                    ]
                )
                nav_links: List[str] = []
                if page_idx > 1:
                    prev_name = "index.md" if page_idx == 2 else f"page-{page_idx - 1}.md"
                    nav_links.append(f"[← Предыдущая]({prev_name})")
                if page_idx < len(pages):
                    next_name = f"page-{page_idx + 1}.md"
                    nav_links.append(f"[Следующая →]({next_name})")
                nav_md = " · ".join(nav_links)
                header = f"# {modules_title}\n"
                if page_idx > 1:
                    header = f"# {modules_title} (страница {page_idx})\n"
                body_parts = []
                if page_idx == 1:
                    body_parts.append(intro)
                body_parts.append("## Список модулей")
                body_parts.append(toc_lines)
                if nav_md:
                    body_parts.append(f"\n{nav_md}\n")
                content = "\n\n".join(body_parts) + "\n"
                out_name = "modules/index.md" if page_idx == 1 else f"modules/page-{page_idx}.md"
                docs_files[out_name] = f"{header}\n{content}"
            regenerated_sections.append(modules_title)
        docs_files.update(module_pages)

    config_pages: Dict[str, str] = {}
    config_nav_paths: List[str] = []
    for path, meta in file_map.items():
        if meta.get("type") != "config":
            continue
        summary_path = meta.get("config_summary_path")
        if not summary_path:
            continue
        config_rel = Path("configs/files") / Path(path)
        config_rel_str = config_rel.as_posix().replace(".", "__") + ".md"
        config_title = Path(path).as_posix()
        summary = read_text_file(Path(summary_path))
        config_pages[config_rel_str] = f"# {config_title}\n\n{summary}\n"
        config_nav_paths.append(config_rel_str)
    if config_nav_paths:
        configs_title = "Конфигурация проекта"
        configs_index_path = docs_dir / "configs" / "index.md"
        if is_forced("configs") or not configs_index_path.exists():
            print(f"[ai-docs] regen section: {configs_title}")
            page_size = 100
            if len(config_nav_paths) > page_size:
                pages = [config_nav_paths[i:i + page_size] for i in range(0, len(config_nav_paths), page_size)]
                total_pages = len(pages)
                for page_idx, page_items in enumerate(pages, start=1):
                    nav_links = []
                    if page_idx > 1:
                        prev_name = "index.md" if page_idx == 2 else f"page-{page_idx - 1}.md"
                        nav_links.append(f"[← Предыдущая]({prev_name})")
                    if page_idx < total_pages:
                        nav_links.append(f"[Следующая →](page-{page_idx + 1}.md)")
                    nav_md = " · ".join(nav_links)
                    header = f"# {configs_title}\n"
                    if page_idx > 1:
                        header = f"# {configs_title} (страница {page_idx})\n"
                    body_parts = [
                        "## Список конфигов",
                        render_project_configs_index(page_items),
                    ]
                    if nav_md:
                        body_parts.append(f"\n{nav_md}\n")
                    content = "\n\n".join(body_parts) + "\n"
                    out_name = "configs/index.md" if page_idx == 1 else f"configs/page-{page_idx}.md"
                    docs_files[out_name] = f"{header}\n{content}"
            else:
                docs_files["configs/index.md"] = f"# {configs_title}\n\n{render_project_configs_index(config_nav_paths)}"
            regenerated_sections.append(configs_title)
        docs_files.update(config_pages)

    if section_tasks:
        await asyncio.gather(*section_tasks)

    configs_dir = docs_dir / "configs"
    if configs_dir.exists():
        for domain in DOMAIN_TITLES.keys():
            if domain not in domain_contexts:
                stale_path = configs_dir / f"{domain}.md"
                if stale_path.exists():
                    stale_path.unlink()

    deps = collect_dependencies(file_map)
    if deps:
        deps_md = "\n".join([f"- {d}" for d in deps])
        docs_files["dependencies.md"] = docs_files.get("dependencies.md", f"# {SECTION_TITLES['dependencies']}\n\n") + f"\n## Выявленные зависимости\n\n{deps_md}\n"

    if "glossary.md" not in docs_files and not (docs_dir / "glossary.md").exists():
        docs_files["glossary.md"] = "# Глоссарий\n\n- TBD\n"
        regenerated_sections.append("Глоссарий")

    if added or modified or deleted:
        changes_context = await build_hierarchical_context(
            llm,
            llm_cache,
            [read_text_file(Path(meta["summary_path"])) for meta in {**added, **modified}.values() if meta.get("summary_path")],
            input_budget,
            language,
            "changes",
            focus="Краткое резюме изменений",
        )
        summary = await generate_section(llm, llm_cache, "Краткое резюме изменений", changes_context, language)
    else:
        summary = "Изменений нет."

    changes_md = format_changes_md(added, modified, deleted, regenerated_sections, summary)
    docs_files["changes.md"] = changes_md

    return (
        docs_files,
        module_pages,
        config_pages,
        module_nav_paths,
        config_nav_paths,
        configs_written,
        regenerated_sections,
        overview_context,
    )
