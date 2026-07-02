import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .changes import format_changes_md
from .generator_shared import (
    SECTION_TITLES,
    DOMAIN_TITLES,
    NavItem,
    collect_dependencies,
    collect_test_info,
    get_cached_text,
    config_doc_path,
    module_doc_path,
    nav_item_doc_path,
    nav_item_label_path,
    render_project_configs_index,
    render_testing_section,
    strip_duplicate_heading,
    is_test_path,
)
from .site_config import format_citation
from .tokenizer import count_tokens, chunk_text
from .utils import read_text_file


DEPENDENCIES_HEADING = "## Выявленные зависимости"
MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class SectionSpec:
    key: str
    title: str
    out_path: str


def _section_specs() -> List[SectionSpec]:
    return [
        SectionSpec(key=key, title=title, out_path=f"{key}.md")
        for key, title in SECTION_TITLES.items()
    ]


def _format_module_toc_line(item: NavItem) -> str:
    href = nav_item_doc_path(item)
    if href.startswith("modules/"):
        href = href[len("modules/") :]
    return f"- [{nav_item_label_path(item)}]({href})"


def _extract_cached_intro(index_path: Path, list_heading: str) -> str:
    if not index_path.exists():
        return ""
    content = read_text_file(index_path)
    lines = content.splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        content = "\n".join(lines[1:]).lstrip()
    heading_idx = content.find(list_heading)
    if heading_idx != -1:
        content = content[:heading_idx]
    return content.strip()


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
    _validate_mermaid_blocks(content, title)
    return strip_duplicate_heading(content, title)


def _validate_mermaid_blocks(content: str, title: str) -> None:
    if title.lower() != "архитектура":
        return
    for block in MERMAID_BLOCK_RE.findall(content):
        if "(" in block or ")" in block:
            raise RuntimeError("Architecture Mermaid block contains parentheses")


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


def _render_dependencies_block(deps: List[str]) -> str:
    deps_md = "\n".join([f"- {dep}" for dep in deps]) if deps else "- нет"
    return f"{DEPENDENCIES_HEADING}\n\n{deps_md}\n"


def _merge_dependencies_block(content: str, deps: List[str]) -> str:
    block = _render_dependencies_block(deps)
    if not content.strip():
        return f"# {SECTION_TITLES['dependencies']}\n\n{block}"

    heading_idx = content.find(DEPENDENCIES_HEADING)
    if heading_idx == -1:
        return f"{content.rstrip()}\n\n{block}"

    next_heading_idx = content.find("\n## ", heading_idx + len(DEPENDENCIES_HEADING))
    prefix = content[:heading_idx].rstrip()
    if next_heading_idx == -1:
        return f"{prefix}\n\n{block}"
    suffix = content[next_heading_idx:].lstrip("\n")
    return f"{prefix}\n\n{block}\n{suffix}"


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


async def _gather_or_cancel(awaitables, label: str):
    tasks = [
        item if isinstance(item, asyncio.Task) else asyncio.create_task(item)
        for item in awaitables
    ]
    if not tasks:
        return []
    try:
        return await asyncio.gather(*tasks)
    except Exception as exc:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise RuntimeError(f"{label}: {exc}") from exc


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
        print(f"[ai-docs] summarize chunks {label}: round {round_idx}, {len(chunks)} chunks")
        results = await _gather_or_cancel(
            [summarize_chunk(llm, llm_cache, chunk, language, focus) for chunk in chunks],
            f"summarize chunks {label}",
        )
        summaries: List[str] = [s for s in results if s]

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
    source_url: Optional[str] = None,
    regen_all_threshold: int = 50,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], List[NavItem], List[NavItem], Dict[str, str], List[str], str]:
    force_sections = {item.strip().lower() for item in (force_sections or set()) if item.strip()}
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

    domain_summaries: Dict[str, List[str]] = {}
    for domain in DOMAIN_TITLES.keys():
        summaries = [
            get_cached_text(m, "summary_path", "summary_text")
            for m in file_map.values()
            if domain in m.get("domains", [])
        ]
        summaries = [s for s in summaries if s]
        if summaries:
            domain_summaries[domain] = summaries

    domain_context_items = await _gather_or_cancel(
        [
            build_hierarchical_context(
                llm,
                llm_cache,
                summaries,
                input_budget,
                language,
                f"domain:{domain}",
                focus=DOMAIN_TITLES.get(domain, domain),
            )
            for domain, summaries in domain_summaries.items()
        ],
        "domain contexts",
    )
    domain_contexts: Dict[str, str] = dict(zip(domain_summaries.keys(), domain_context_items))

    test_paths, test_commands = collect_test_info(file_map)

    all_summaries = [
        get_cached_text(m, "summary_path", "summary_text")
        for m in file_map.values()
        if m.get("summary_path")
    ]

    docs_files: Dict[str, str] = {}
    overview_path = docs_dir / "overview.md"
    overview_forced = is_forced("overview", "section:overview", "overview.md")
    should_regen_overview = overview_forced or force_all or not overview_path.exists()

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

    pending_sections: List[SectionSpec] = []
    for spec in _section_specs():
        section_path = docs_dir / spec.out_path
        forced = is_forced(spec.key, spec.title, f"section:{spec.key}", f"section:{spec.title}")
        if forced or not section_path.exists():
            if spec.key == "testing":
                print(f"[ai-docs] regen section: {spec.title}")
                docs_files[spec.out_path] = f"# {spec.title}\n\n{render_testing_section(test_paths, test_commands)}\n"
                regenerated_sections.append(spec.title)
                continue
            pending_sections.append(spec)

    index_title = "Документация проекта"
    index_path = docs_dir / "index.md"
    pending_index = is_forced("index", "docs", "documentation") or not index_path.exists()

    context_specs: List[Tuple[str, List[str], str, str, str]] = []
    if should_regen_overview:
        context_specs.append(("overview", all_summaries, "overview", "Обзор проекта", ""))
    for spec in pending_sections:
        context_specs.append((f"section:{spec.key}", all_summaries, f"section:{spec.key}", spec.title, ""))
    if pending_index:
        context_specs.append(("index", all_summaries, "section:index", index_title, ""))

    context_results = await _gather_or_cancel(
        [
            build_hierarchical_context(
                llm,
                llm_cache,
                summaries,
                input_budget,
                language,
                label,
                focus=focus,
            )
            for _, summaries, label, focus, _ in context_specs
        ],
        "section contexts",
    )
    contexts: Dict[str, str] = {key: ctx for (key, _, _, _, _), ctx in zip(context_specs, context_results)}

    if should_regen_overview:
        print("[ai-docs] regen section: overview")
        overview_context = contexts["overview"]
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

    for spec in pending_sections:
        submit_section(spec.out_path, spec.title, contexts[f"section:{spec.key}"])

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

    if pending_index:
        print(f"[ai-docs] regen section: {index_title}")
        submit_section("index.md", index_title, contexts["index"])

    module_summaries = []
    module_nav_paths: List[NavItem] = []
    for path, meta in file_map.items():
        if is_test_path(path):
            continue
        summary_path = meta.get("module_summary_path")
        if not summary_path:
            continue
        module_rel_str = module_doc_path(path)
        module_title = Path(path).with_suffix("").as_posix()
        summary = get_cached_text(meta, "module_summary_path", "module_summary_text")
        citation = format_citation(path, source_url)
        module_pages[module_rel_str] = f"# {module_title}\n\n{citation}\n\n{summary}\n"
        module_nav_paths.append((module_rel_str, path))
        module_summaries.append(summary)
    if module_summaries:
        modules_title = "Модули"
        sorted_modules = sorted(module_nav_paths, key=lambda item: nav_item_label_path(item).lower())
        per_page = 100
        total = len(sorted_modules)
        pages = [sorted_modules[i : i + per_page] for i in range(0, total, per_page)]
        modules_index_path = docs_dir / "modules" / "index.md"
        modules_intro_forced = is_forced("modules") or not modules_index_path.exists()

        async def build_modules_pages() -> None:
            if modules_intro_forced:
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
                async with section_sem:
                    intro = await generate_section(llm, llm_cache, modules_title, modules_context, language)
                regenerated_sections.append(modules_title)
            else:
                intro = _extract_cached_intro(modules_index_path, "## Список модулей")
            for page_idx, page_items in enumerate(pages, start=1):
                toc_lines = "\n".join(
                    [
                        _format_module_toc_line(item)
                        for item in page_items
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
                if page_idx == 1 and intro:
                    body_parts.append(intro)
                body_parts.append("## Список модулей")
                body_parts.append(toc_lines)
                if nav_md:
                    body_parts.append(f"\n{nav_md}\n")
                content = "\n\n".join(body_parts) + "\n"
                out_name = "modules/index.md" if page_idx == 1 else f"modules/page-{page_idx}.md"
                docs_files[out_name] = f"{header}\n{content}"

        section_tasks.append(asyncio.create_task(build_modules_pages()))
        docs_files.update(module_pages)

    config_pages: Dict[str, str] = {}
    config_nav_paths: List[NavItem] = []
    for path, meta in file_map.items():
        if meta.get("type") != "config":
            continue
        summary_path = meta.get("config_summary_path")
        if not summary_path:
            continue
        config_rel_str = config_doc_path(path)
        config_title = Path(path).as_posix()
        summary = get_cached_text(meta, "config_summary_path", "config_summary_text")
        citation = format_citation(path, source_url)
        config_pages[config_rel_str] = f"# {config_title}\n\n{citation}\n\n{summary}\n"
        config_nav_paths.append((config_rel_str, path))
    if config_nav_paths:
        configs_title = "Конфигурация проекта"
        configs_index_path = docs_dir / "configs" / "index.md"
        if is_forced("configs") or not configs_index_path.exists():
            print(f"[ai-docs] regen section: {configs_title}")
            regenerated_sections.append(configs_title)
        page_size = 100
        sorted_configs = sorted(config_nav_paths, key=lambda item: nav_item_label_path(item).lower())
        if len(sorted_configs) > page_size:
            pages = [sorted_configs[i:i + page_size] for i in range(0, len(sorted_configs), page_size)]
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
        docs_files.update(config_pages)

    changes_summary_task: Optional[asyncio.Task] = None
    if added or modified or deleted:
        changes_inputs = [
            get_cached_text(meta, "summary_path", "summary_text")
            for meta in {**added, **modified}.values()
            if meta.get("summary_path")
        ]

        async def build_changes_summary() -> str:
            changes_context = await build_hierarchical_context(
                llm,
                llm_cache,
                changes_inputs,
                input_budget,
                language,
                "changes",
                focus="Краткое резюме изменений",
            )
            async with section_sem:
                return await generate_section(
                    llm, llm_cache, "Краткое резюме изменений", changes_context, language
                )

        changes_summary_task = asyncio.create_task(build_changes_summary())
        section_tasks.append(changes_summary_task)
    else:
        changes_summary = "Изменений нет."

    if section_tasks:
        await _gather_or_cancel(section_tasks, "section tasks")
    if changes_summary_task is not None:
        changes_summary = changes_summary_task.result()

    configs_dir = docs_dir / "configs"
    if configs_dir.exists():
        for domain in DOMAIN_TITLES.keys():
            if domain not in domain_contexts:
                stale_path = configs_dir / f"{domain}.md"
                if stale_path.exists():
                    stale_path.unlink()

    deps = collect_dependencies(file_map)
    dependencies_content = docs_files.get("dependencies.md")
    dependencies_path = docs_dir / "dependencies.md"
    if dependencies_content is not None or dependencies_path.exists() or deps:
        if dependencies_content is None:
            if dependencies_path.exists():
                dependencies_content = read_text_file(dependencies_path)
            else:
                dependencies_content = f"# {SECTION_TITLES['dependencies']}\n\n"
        docs_files["dependencies.md"] = _merge_dependencies_block(dependencies_content, deps)

    if "glossary.md" not in docs_files and not (docs_dir / "glossary.md").exists():
        docs_files["glossary.md"] = "# Глоссарий\n\n- TBD\n"
        regenerated_sections.append("Глоссарий")

    changes_md = format_changes_md(added, modified, deleted, regenerated_sections, changes_summary)
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
