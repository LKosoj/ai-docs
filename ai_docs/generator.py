import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import tomli
import yaml

from concurrent.futures import ThreadPoolExecutor, as_completed

from .cache import CacheManager
from .changes import format_changes_md
from .domain import is_infra
from .llm import LLMClient
from .mkdocs import build_mkdocs_yaml, write_docs_files
from .summary import summarize_file, write_summary
from .tokenizer import count_tokens, chunk_text
from .utils import ensure_dir, read_text_file, sha256_text, safe_slug


SECTION_TITLES = {
    "architecture": "Архитектура",
    "runtime": "Запуск и окружение",
    "dependencies": "Зависимости",
    "conventions": "Соглашения",
    "glossary": "Глоссарий",
}

DOMAIN_TITLES = {
    "kubernetes": "Kubernetes",
    "helm": "Helm",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "docker": "Docker",
    "ci": "CI/CD",
}


def _collect_dependencies(files: Dict[str, Dict]) -> List[str]:
    deps: List[str] = []
    for path, meta in files.items():
        if path.endswith("pyproject.toml"):
            try:
                data = tomli.loads(meta["content"])
                deps_map = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
                deps.extend([f"{k} {v}" for k, v in deps_map.items()])
            except Exception:
                continue
        if path.endswith("requirements.txt"):
            lines = [line.strip() for line in meta["content"].splitlines() if line.strip() and not line.strip().startswith("#")]
            deps.extend(lines)
        if path.endswith("package.json"):
            try:
                data = json.loads(meta["content"])
                for section in ("dependencies", "devDependencies"):
                    for k, v in data.get(section, {}).items():
                        deps.append(f"{k} {v}")
            except Exception:
                continue
    return sorted(set(deps))


def _generate_section(llm: LLMClient, llm_cache: Dict[str, str], title: str, context: str, language: str) -> str:
    prompt = (
        "Ты опытный технический писатель. Сгенерируй раздел документации в Markdown. "
        f"Язык: {language}. Раздел: {title}. "
        "Используй предоставленный контекст. Избегай воды, дай практические детали."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": context},
    ]
    content = llm.chat(messages, cache=llm_cache).strip()
    return _strip_duplicate_heading(content, title)


def _strip_duplicate_heading(content: str, title: str) -> str:
    lines = content.splitlines()
    if not lines:
        return content
    first = lines[0].strip()
    if first.startswith("#") and first.lstrip("#").strip().lower() == title.strip().lower():
        return "\n".join(lines[1:]).lstrip()
    return content


def _generate_readme(llm: LLMClient, llm_cache: Dict[str, str], project_name: str, overview_context: str, language: str) -> str:
    prompt = (
        "Сформируй README.md для проекта. "
        "Структура: Обзор, Быстрый старт, Архитектура (кратко), Ссылки на docs. "
        "Текст должен быть кратким и полезным. Язык: " + language
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": overview_context},
    ]
    return llm.chat(messages, cache=llm_cache).strip()


def _truncate_context(context: str, model: str, max_tokens: int) -> str:
    if count_tokens(context, model) <= max_tokens:
        return context
    chunks = chunk_text(context, model=model, max_tokens=max_tokens)
    return chunks[0]


def generate_docs(
    files: List[Dict],
    output_root: Path,
    cache_dir: Path,
    llm: LLMClient,
    language: str,
    write_readme: bool,
    write_mkdocs: bool,
    use_cache: bool = True,
    threads: int = 1,
    local_site: bool = False,
) -> None:
    cache = CacheManager(cache_dir)
    llm_cache = cache.load_llm_cache() if use_cache else None

    file_map: Dict[str, Dict] = {}
    for f in files:
        file_map[f["path"]] = {
            "hash": sha256_text(f["content"]),
            "size": f["size"],
            "type": f["type"],
            "domains": f["domains"],
            "content": f["content"],
        }

    added, modified, deleted, unchanged = cache.diff_files(file_map)
    print(f"[ai-docs] diff: added={len(added)} modified={len(modified)} deleted={len(deleted)} unchanged={len(unchanged)}")

    summaries_dir = cache_dir / "intermediate" / "files"
    ensure_dir(summaries_dir)

    # Summaries for changed files (parallel if threads > 1)
    to_summarize: List[Tuple[str, Dict]] = list({**added, **modified}.items())
    if to_summarize:
        print(f"[ai-docs] summarize: {len(to_summarize)} changed files (threads={threads})")
    if threads > 1 and to_summarize:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    summarize_file,
                    meta["content"],
                    meta["type"],
                    meta["domains"],
                    llm,
                    llm_cache,
                    llm.model,
                ): (path, meta)
                for path, meta in to_summarize
            }
            total = len(futures)
            done = 0
            for future in as_completed(futures):
                path, meta = futures[future]
                print(f"[ai-docs] summarize start: {path}")
                summary = future.result()
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize done: {path} ({done}/{total})")
    else:
        total = len(to_summarize)
        done = 0
        for path, meta in to_summarize:
            print(f"[ai-docs] summarize start: {path}")
            summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model)
            summary_path = write_summary(summaries_dir, path, summary)
            meta["summary_path"] = str(summary_path)
            done += 1
            print(f"[ai-docs] summarize done: {path} ({done}/{total})")

    # Carry summaries for unchanged files
    index_data = cache.load_index()
    prev_files = index_data.get("files", {})
    missing_summaries: List[Tuple[str, Dict]] = []
    for path, meta in unchanged.items():
        prev = prev_files.get(path, {})
        if "summary_path" in prev:
            meta["summary_path"] = prev["summary_path"]
        else:
            missing_summaries.append((path, meta))

    if missing_summaries:
        print(f"[ai-docs] summarize: {len(missing_summaries)} missing summaries")
        if threads > 1:
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                    ): (path, meta)
                    for path, meta in missing_summaries
                }
                total = len(futures)
                done = 0
                for future in as_completed(futures):
                    path, meta = futures[future]
                    print(f"[ai-docs] summarize start: {path}")
                    summary = future.result()
                    summary_path = write_summary(summaries_dir, path, summary)
                    meta["summary_path"] = str(summary_path)
                    done += 1
                    print(f"[ai-docs] summarize done: {path} ({done}/{total})")
        else:
            total = len(missing_summaries)
            done = 0
            for path, meta in missing_summaries:
                print(f"[ai-docs] summarize start: {path}")
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model)
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize done: {path} ({done}/{total})")

    # Remove summaries for deleted files
    if deleted:
        print(f"[ai-docs] cleanup: removing {len(deleted)} deleted summaries")
        for path, meta in deleted.items():
            prev_meta = prev_files.get(path, {})
            summary_path = prev_meta.get("summary_path")
            if summary_path:
                try:
                    Path(summary_path).unlink()
                except FileNotFoundError:
                    pass
            prev_files.pop(path, None)

    input_budget = max(512, llm.context_limit - llm.max_tokens - 200)

    # Domains changed
    changed_domains: Set[str] = set()
    for path, meta in {**added, **modified, **deleted}.items():
        changed_domains.update(meta.get("domains", []))

    # Prepare domain contexts
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
            domain_contexts[domain] = _truncate_context("\n\n".join(summaries), llm.model, input_budget)

    # Base context for overview sections
    overview_context = "\n\n".join(
        [read_text_file(Path(m["summary_path"])) for m in file_map.values() if m.get("summary_path")]
    )
    overview_context = _truncate_context(overview_context, llm.model, input_budget)

    # Sections to regenerate
    regenerated_sections: List[str] = []
    docs_files: Dict[str, str] = {}
    docs_dir = output_root / "docs"

    # Core sections
    for key, title in SECTION_TITLES.items():
        if added or modified or deleted or not (docs_dir / f"{key}.md").exists():
            print(f"[ai-docs] generate section: {title}")
            content = _generate_section(llm, llm_cache, title, overview_context, language)
            docs_files[f"{key}.md"] = f"# {title}\n\n{content}\n"
            regenerated_sections.append(title)

    # Domain sections
    configs_written: Dict[str, str] = {}
    for domain, title in DOMAIN_TITLES.items():
        if domain not in domain_contexts:
            continue
        filename = f"{domain}.md"
        if domain in changed_domains or not (docs_dir / "configs" / filename).exists():
            print(f"[ai-docs] generate domain: {title}")
            content = _generate_section(llm, llm_cache, title, domain_contexts[domain], language)
            docs_files[f"configs/{filename}"] = f"# {title}\n\n{content}\n"
            regenerated_sections.append(title)
        configs_written[domain] = filename

    # Remove stale config docs if domain no longer present
    configs_dir = docs_dir / "configs"
    if configs_dir.exists():
        for domain, title in DOMAIN_TITLES.items():
            if domain not in domain_contexts:
                stale_path = configs_dir / f"{domain}.md"
                if stale_path.exists():
                    stale_path.unlink()

    # Index
    index_title = "Документация проекта"
    if added or modified or deleted or not (docs_dir / "index.md").exists():
        print("[ai-docs] generate index")
        intro = _generate_section(llm, llm_cache, index_title, overview_context, language)
        docs_files["index.md"] = f"# {index_title}\n\n{intro}\n"
        regenerated_sections.append(index_title)

    # Dependencies (inject list if found)
    deps = _collect_dependencies(file_map)
    if deps:
        deps_md = "\n".join([f"- {d}" for d in deps])
        docs_files["dependencies.md"] = docs_files.get("dependencies.md", f"# {SECTION_TITLES['dependencies']}\n\n") + f"\n## Выявленные зависимости\n\n{deps_md}\n"

    # Glossary placeholder if missing
    if "glossary.md" not in docs_files and not (docs_dir / "glossary.md").exists():
        docs_files["glossary.md"] = "# Глоссарий\n\n- TBD\n"
        regenerated_sections.append("Глоссарий")

    # Changes summary
    if added or modified or deleted:
        print("[ai-docs] generate changes")
        changes_context = "\n\n".join(
            [read_text_file(Path(meta["summary_path"])) for meta in {**added, **modified}.values() if meta.get("summary_path")]
        )
        changes_context = _truncate_context(changes_context, llm.model, input_budget)
        summary = _generate_section(llm, llm_cache, "Краткое резюме изменений", changes_context, language)
    else:
        summary = "Изменений нет."

    changes_md = format_changes_md(added, modified, deleted, regenerated_sections, summary)
    docs_files["changes.md"] = changes_md

    write_docs_files(docs_dir, docs_files)

    if write_readme:
        print("[ai-docs] write README")
        readme = _generate_readme(llm, llm_cache, output_root.name, overview_context, language)
        (output_root / "README.md").write_text(readme + "\n", encoding="utf-8")

    # Remove orphan docs (keep docs/plans)
    if docs_dir.exists():
        print("[ai-docs] cleanup docs: removing orphan files")
        keep_files = {docs_dir / rel for rel in docs_files.keys()}
        keep_dirs = {docs_dir / "plans"}
        for path in docs_dir.rglob("*"):
            if path.is_dir():
                continue
            if any(str(path).startswith(str(keep_dir)) for keep_dir in keep_dirs):
                continue
            if path in keep_files:
                continue
            path.unlink()

    if write_mkdocs:
        print("[ai-docs] mkdocs: build")
        mkdocs_yaml = build_mkdocs_yaml(
            site_name=output_root.name,
            sections=SECTION_TITLES,
            configs=configs_written,
            local_site=local_site,
        )
        (output_root / "mkdocs.yml").write_text(mkdocs_yaml, encoding="utf-8")
        mkdocs_bin = shutil.which("mkdocs")
        if not mkdocs_bin:
            raise RuntimeError("mkdocs is not installed or not on PATH")
        subprocess.check_call([mkdocs_bin, "build", "-f", "mkdocs.yml"], cwd=output_root)
        print("[ai-docs] mkdocs: done")

    # Save cache
    new_index = {
        "files": {path: {k: v for k, v in meta.items() if k != "content"} for path, meta in file_map.items()},
        "sections": {"regenerated": regenerated_sections},
    }
    cache.save_index(new_index)
    if use_cache and llm_cache is not None:
        cache.save_llm_cache(llm_cache)
