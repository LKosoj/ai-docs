import json
from datetime import datetime
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
    "testing": "Тестирование",
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
    "observability": "Observability",
    "service_mesh": "Service Mesh / Ingress",
    "data_storage": "Data / Storage",
}

def _is_test_path(path: str) -> bool:
    parts = Path(path).parts
    if any(part in {"test", "tests", "__tests__"} for part in parts):
        return True
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")


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


def _collect_test_info(files: Dict[str, Dict]) -> Tuple[List[str], List[str]]:
    test_paths = sorted([path for path in files if _is_test_path(path)])
    commands: List[str] = []

    has_pytest_config = any(
        path.endswith("pytest.ini") or path.endswith("pyproject.toml")
        for path in files.keys()
    )
    has_pytest_dep = False
    for path, meta in files.items():
        if path.endswith(("requirements.txt", "pyproject.toml")):
            content = meta.get("content", "")
            if "pytest" in content:
                has_pytest_dep = True
                break

    if test_paths and (has_pytest_config or has_pytest_dep or any(p.endswith(".py") for p in test_paths)):
        commands.append("python -m pytest")

    for path, meta in files.items():
        if path.endswith("package.json"):
            try:
                data = json.loads(meta.get("content", ""))
                scripts = data.get("scripts", {})
                if "test" in scripts:
                    commands.append("npm test")
            except Exception:
                continue

    return test_paths, sorted(set(commands))


def _render_testing_section(test_paths: List[str], commands: List[str]) -> str:
    if not test_paths:
        return "Тесты не обнаружены."
    tests_md = "\n".join(f"- `{p}`" for p in test_paths)
    commands_md = "\n".join(f"- `{c}`" for c in commands) if commands else "- (команда запуска не определена)"
    return (
        "## Найденные тесты\n\n"
        f"{tests_md}\n\n"
        "## Как запускать\n\n"
        f"{commands_md}\n"
    )


def _render_project_configs_index(config_nav_paths: List[str]) -> str:
    if not config_nav_paths:
        return "Конфигурационные файлы не обнаружены."
    toc_lines = "\n".join(
        [
            f"- [{Path(p).with_suffix('').as_posix()}]({Path(p).as_posix()[len('configs/'):] if p.startswith('configs/') else p})"
            for p in sorted(config_nav_paths)
        ]
    )
    return f"## Файлы конфигурации\n\n{toc_lines}\n"


def _generate_section(llm: LLMClient, llm_cache: Dict[str, str], title: str, context: str, language: str) -> str:
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


def _first_paragraph(text: str) -> str:
    lines: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith("#") or line.startswith("```"):
            continue
        lines.append(line)
        if len(lines) >= 2:
            break
    return " ".join(lines).strip()


def _build_docs_index(
    output_root: Path,
    docs_dir: Path,
    docs_files: Dict[str, str],
    file_map: Dict[str, Dict],
    module_pages: Dict[str, str],
    config_pages: Dict[str, str],
) -> Dict[str, object]:
    existing_files: Set[str] = set()
    if docs_dir.exists():
        for path in docs_dir.rglob("*.md"):
            try:
                existing_files.add(path.relative_to(docs_dir).as_posix())
            except Exception:
                continue
    sections = []
    for key, title in SECTION_TITLES.items():
        path = f"{key}.md"
        if path in docs_files or path in existing_files:
            sections.append({"id": key, "title": title, "path": path})
    if "configs/index.md" in docs_files or "configs/index.md" in existing_files:
        sections.append({"id": "configs", "title": "Конфигурация проекта", "path": "configs/index.md"})

    modules = []
    for path, meta in file_map.items():
        if _is_test_path(path):
            continue
        summary_path = meta.get("module_summary_path")
        if not summary_path:
            continue
        module_rel = Path("modules") / Path(path).with_suffix("")
        module_rel_str = module_rel.as_posix() + ".md"
        summary_text = read_text_file(Path(summary_path))
        modules.append(
            {
                "name": Path(path).with_suffix("").as_posix(),
                "path": module_rel_str,
                "source_path": path,
                "summary": _first_paragraph(summary_text),
            }
        )

    configs = []
    for path, meta in file_map.items():
        if meta.get("type") != "config":
            continue
        summary_path = meta.get("config_summary_path")
        if not summary_path:
            continue
        config_rel = Path("configs/files") / Path(path)
        config_rel_str = config_rel.as_posix().replace(".", "__") + ".md"
        summary_text = read_text_file(Path(summary_path))
        configs.append(
            {
                "name": Path(path).as_posix(),
                "path": config_rel_str,
                "source_path": path,
                "summary": _first_paragraph(summary_text),
            }
        )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "docs_dir": ".ai-docs",
        "rules": {
            "priority": [
                "modules/index.md",
                "modules/*",
                "configs/index.md",
                "configs/files/*",
                "index.md",
                "architecture.md",
                "conventions.md",
            ],
            "ranking": "keyword frequency + file priority",
            "usage": "use this index to choose a narrow route before reading full docs",
        },
        "sections": sections,
        "modules": modules,
        "configs": configs,
        "files": sorted(set(docs_files.keys()) | existing_files | {"_index.json"}),
    }


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
    force: bool = False,
) -> None:
    cache = CacheManager(cache_dir)
    llm_cache = cache.load_llm_cache() if use_cache else None
    index_data = cache.load_index()
    prev_files = index_data.get("files", {})
    errors: List[str] = []

    def _save_cache_snapshot() -> None:
        snapshot = {
            "files": {path: {k: v for k, v in meta.items() if k != "content"} for path, meta in file_map.items()},
            "sections": index_data.get("sections", {}),
        }
        cache.save_index(snapshot)
        if use_cache and llm_cache is not None:
            cache.save_llm_cache(llm_cache)

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
    module_summaries_dir = cache_dir / "intermediate" / "modules"
    ensure_dir(summaries_dir)
    ensure_dir(module_summaries_dir)

    # Summaries for changed files (parallel if threads > 1)
    to_summarize: List[Tuple[str, Dict]] = list({**added, **modified}.items())
    if to_summarize:
        print(f"[ai-docs] summarize: {len(to_summarize)} changed files (threads={threads})")
    if threads > 1 and to_summarize:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            print(f"[ai-docs] summarize: queued {len(to_summarize)} tasks (workers={threads})")
            for path, meta in to_summarize:
                print(f"[ai-docs] summarize start: {path}")
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        False,
                    )
                ] = (path, meta)
            total = len(futures)
            done = 0
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    msg = f"summarize: {path} -> {exc}"
                    print(f"[ai-docs] summarize error: {path} ({exc})")
                    errors.append(msg)
                    continue
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize done: {path} ({done}/{total})")
    else:
        total = len(to_summarize)
        done = 0
        for path, meta in to_summarize:
            print(f"[ai-docs] summarize start: {path}")
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, False)
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize done: {path} ({done}/{total})")
            except Exception as exc:
                msg = f"summarize: {path} -> {exc}"
                print(f"[ai-docs] summarize error: {path} ({exc})")
                errors.append(msg)
    if to_summarize:
        _save_cache_snapshot()

    # Detailed module summaries for changed files (code only)
    module_candidates = [
        (path, meta)
        for path, meta in to_summarize
        if meta.get("type") == "code" and not _is_test_path(path)
    ]
    if module_candidates:
        print(f"[ai-docs] summarize modules: {len(module_candidates)} changed code files (threads={threads})")
    if threads > 1 and module_candidates:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            print(f"[ai-docs] summarize modules: queued {len(module_candidates)} tasks (workers={threads})")
            for path, meta in module_candidates:
                print(f"[ai-docs] summarize module start: {path}")
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        True,
                    )
                ] = (path, meta)
            total = len(futures)
            done = 0
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    msg = f"summarize module: {path} -> {exc}"
                    print(f"[ai-docs] summarize module error: {path} ({exc})")
                    errors.append(msg)
                    continue
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize module done: {path} ({done}/{total})")
    else:
        total = len(module_candidates)
        done = 0
        for path, meta in module_candidates:
            print(f"[ai-docs] summarize module start: {path}")
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize module done: {path} ({done}/{total})")
            except Exception as exc:
                msg = f"summarize module: {path} -> {exc}"
                print(f"[ai-docs] summarize module error: {path} ({exc})")
                errors.append(msg)
    if module_candidates:
        _save_cache_snapshot()

    # Detailed config summaries for changed files (config only)
    config_candidates = [
        (path, meta)
        for path, meta in to_summarize
        if meta.get("type") == "config"
    ]
    config_summaries_dir = cache_dir / "intermediate" / "configs"
    if config_candidates:
        print(f"[ai-docs] summarize configs: {len(config_candidates)} changed config files (threads={threads})")
    if threads > 1 and config_candidates:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            print(f"[ai-docs] summarize configs: queued {len(config_candidates)} tasks (workers={threads})")
            for path, meta in config_candidates:
                print(f"[ai-docs] summarize config start: {path}")
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        True,
                    )
                ] = (path, meta)
            total = len(futures)
            done = 0
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    msg = f"summarize config: {path} -> {exc}"
                    print(f"[ai-docs] summarize config error: {path} ({exc})")
                    errors.append(msg)
                    continue
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize config done: {path} ({done}/{total})")
    else:
        total = len(config_candidates)
        done = 0
        for path, meta in config_candidates:
            print(f"[ai-docs] summarize config start: {path}")
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                done += 1
                print(f"[ai-docs] summarize config done: {path} ({done}/{total})")
            except Exception as exc:
                msg = f"summarize config: {path} -> {exc}"
                print(f"[ai-docs] summarize config error: {path} ({exc})")
                errors.append(msg)
    if config_candidates:
        _save_cache_snapshot()

    # Carry summaries for unchanged files (recreate if missing)
    missing_summaries: List[Tuple[str, Dict]] = []
    missing_module_summaries: List[Tuple[str, Dict]] = []
    missing_config_summaries: List[Tuple[str, Dict]] = []
    for path, meta in unchanged.items():
        prev = prev_files.get(path, {})
        summary_path = prev.get("summary_path")
        if summary_path and Path(summary_path).exists():
            meta["summary_path"] = summary_path
        else:
            if summary_path:
                print(f"[ai-docs] summarize missing: {path} ({summary_path})")
            else:
                print(f"[ai-docs] summarize missing: {path}")
            missing_summaries.append((path, meta))
        module_summary_path = prev.get("module_summary_path")
        if meta.get("type") == "code" and not _is_test_path(path):
            if module_summary_path and Path(module_summary_path).exists():
                meta["module_summary_path"] = module_summary_path
            else:
                if module_summary_path:
                    print(f"[ai-docs] summarize module missing: {path} ({module_summary_path})")
                else:
                    print(f"[ai-docs] summarize module missing: {path}")
                missing_module_summaries.append((path, meta))
        config_summary_path = prev.get("config_summary_path")
        if meta.get("type") == "config":
            if config_summary_path and Path(config_summary_path).exists():
                meta["config_summary_path"] = config_summary_path
            else:
                if config_summary_path:
                    print(f"[ai-docs] summarize config missing: {path} ({config_summary_path})")
                else:
                    print(f"[ai-docs] summarize config missing: {path}")
                missing_config_summaries.append((path, meta))

    if missing_summaries:
        print(f"[ai-docs] summarize: {len(missing_summaries)} missing summaries")
        if threads > 1:
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {}
                print(f"[ai-docs] summarize: queued {len(missing_summaries)} tasks (workers={threads})")
                for path, meta in missing_summaries:
                    print(f"[ai-docs] summarize start: {path}")
                    futures[
                        executor.submit(
                            summarize_file,
                            meta["content"],
                            meta["type"],
                            meta["domains"],
                            llm,
                            llm_cache,
                            llm.model,
                        )
                    ] = (path, meta)
                total = len(futures)
                done = 0
                for future in as_completed(futures):
                    path, meta = futures[future]
                    try:
                        summary = future.result()
                    except Exception as exc:
                        msg = f"summarize: {path} -> {exc}"
                        print(f"[ai-docs] summarize error: {path} ({exc})")
                        errors.append(msg)
                        continue
                    summary_path = write_summary(summaries_dir, path, summary)
                    meta["summary_path"] = str(summary_path)
                    done += 1
                    print(f"[ai-docs] summarize done: {path} ({done}/{total})")
        else:
            total = len(missing_summaries)
            done = 0
            for path, meta in missing_summaries:
                print(f"[ai-docs] summarize start: {path}")
                try:
                    summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, False)
                    summary_path = write_summary(summaries_dir, path, summary)
                    meta["summary_path"] = str(summary_path)
                    done += 1
                    print(f"[ai-docs] summarize done: {path} ({done}/{total})")
                except Exception as exc:
                    msg = f"summarize: {path} -> {exc}"
                    print(f"[ai-docs] summarize error: {path} ({exc})")
                    errors.append(msg)
        _save_cache_snapshot()

    if missing_module_summaries:
        print(f"[ai-docs] summarize modules: {len(missing_module_summaries)} missing module summaries")
        if threads > 1:
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {}
                print(f"[ai-docs] summarize modules: queued {len(missing_module_summaries)} tasks (workers={threads})")
                for path, meta in missing_module_summaries:
                    print(f"[ai-docs] summarize module start: {path}")
                    futures[
                        executor.submit(
                            summarize_file,
                            meta["content"],
                            meta["type"],
                            meta["domains"],
                            llm,
                            llm_cache,
                            llm.model,
                            True,
                        )
                    ] = (path, meta)
                total = len(futures)
                done = 0
                for future in as_completed(futures):
                    path, meta = futures[future]
                    try:
                        summary = future.result()
                    except Exception as exc:
                        msg = f"summarize module: {path} -> {exc}"
                        print(f"[ai-docs] summarize module error: {path} ({exc})")
                        errors.append(msg)
                        continue
                    summary_path = write_summary(module_summaries_dir, path, summary)
                    meta["module_summary_path"] = str(summary_path)
                    done += 1
                    print(f"[ai-docs] summarize module done: {path} ({done}/{total})")
        else:
            total = len(missing_module_summaries)
            done = 0
            for path, meta in missing_module_summaries:
                print(f"[ai-docs] summarize module start: {path}")
                try:
                    summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                    summary_path = write_summary(module_summaries_dir, path, summary)
                    meta["module_summary_path"] = str(summary_path)
                    done += 1
                    print(f"[ai-docs] summarize module done: {path} ({done}/{total})")
                except Exception as exc:
                    msg = f"summarize module: {path} -> {exc}"
                    print(f"[ai-docs] summarize module error: {path} ({exc})")
                    errors.append(msg)
        _save_cache_snapshot()

    if missing_config_summaries:
        print(f"[ai-docs] summarize configs: {len(missing_config_summaries)} missing config summaries")
        if threads > 1:
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {}
                print(f"[ai-docs] summarize configs: queued {len(missing_config_summaries)} tasks (workers={threads})")
                for path, meta in missing_config_summaries:
                    print(f"[ai-docs] summarize config start: {path}")
                    futures[
                        executor.submit(
                            summarize_file,
                            meta["content"],
                            meta["type"],
                            meta["domains"],
                            llm,
                            llm_cache,
                            llm.model,
                            True,
                        )
                    ] = (path, meta)
                total = len(futures)
                done = 0
                for future in as_completed(futures):
                    path, meta = futures[future]
                    try:
                        summary = future.result()
                    except Exception as exc:
                        msg = f"summarize config: {path} -> {exc}"
                        print(f"[ai-docs] summarize config error: {path} ({exc})")
                        errors.append(msg)
                        continue
                    summary_path = write_summary(config_summaries_dir, path, summary)
                    meta["config_summary_path"] = str(summary_path)
                    done += 1
                    print(f"[ai-docs] summarize config done: {path} ({done}/{total})")
        else:
            total = len(missing_config_summaries)
            done = 0
            for path, meta in missing_config_summaries:
                print(f"[ai-docs] summarize config start: {path}")
                try:
                    summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                    summary_path = write_summary(config_summaries_dir, path, summary)
                    meta["config_summary_path"] = str(summary_path)
                    done += 1
                    print(f"[ai-docs] summarize config done: {path} ({done}/{total})")
                except Exception as exc:
                    msg = f"summarize config: {path} -> {exc}"
                    print(f"[ai-docs] summarize config error: {path} ({exc})")
                    errors.append(msg)
        _save_cache_snapshot()

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
            module_summary_path = prev_meta.get("module_summary_path")
            if module_summary_path:
                try:
                    Path(module_summary_path).unlink()
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

    test_paths, test_commands = _collect_test_info(file_map)

    # Base context for overview sections
    overview_context = "\n\n".join(
        [read_text_file(Path(m["summary_path"])) for m in file_map.values() if m.get("summary_path")]
    )
    overview_context = _truncate_context(overview_context, llm.model, input_budget)

    # Sections to regenerate
    regenerated_sections: List[str] = []
    docs_files: Dict[str, str] = {}
    docs_dir = output_root / ".ai-docs"
    module_pages: Dict[str, str] = {}
    section_workers = min(threads, 4) if threads > 1 else 1

    # Core + domain sections (+ index) in parallel (bounded)
    configs_written: Dict[str, str] = {}
    section_futures = {}
    if section_workers > 1:
        executor = ThreadPoolExecutor(max_workers=section_workers)
    else:
        executor = None

    def _submit_section(out_path: str, title: str, context: str) -> None:
        if executor:
            section_futures[executor.submit(_generate_section, llm, llm_cache, title, context, language)] = (out_path, title)
        else:
            content = _generate_section(llm, llm_cache, title, context, language)
            docs_files[out_path] = f"# {title}\n\n{content}\n"
            regenerated_sections.append(title)

    # Core sections
    for key, title in SECTION_TITLES.items():
        if added or modified or deleted or not (docs_dir / f"{key}.md").exists():
            print(f"[ai-docs] generate section: {title}")
            if key == "testing":
                docs_files["testing.md"] = f"# {title}\n\n{_render_testing_section(test_paths, test_commands)}\n"
                regenerated_sections.append(title)
                continue
            _submit_section(f"{key}.md", title, overview_context)

    # Domain sections
    for domain, title in DOMAIN_TITLES.items():
        if domain not in domain_contexts:
            continue
        filename = f"{domain}.md"
        if domain in changed_domains or not (docs_dir / "configs" / filename).exists():
            print(f"[ai-docs] generate domain: {title}")
            _submit_section(f"configs/{filename}", title, domain_contexts[domain])
        configs_written[domain] = filename

    # Index
    index_title = "Документация проекта"
    if added or modified or deleted or not (docs_dir / "index.md").exists():
        print("[ai-docs] generate index")
        _submit_section("index.md", index_title, overview_context)

    # Modules (detailed summaries -> per-module pages + index)
    module_summaries = []
    module_nav_paths: List[str] = []
    for path, meta in file_map.items():
        if _is_test_path(path):
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
        modules_context = _truncate_context("\n\n".join(module_summaries), llm.model, input_budget)
        print("[ai-docs] generate modules")
        intro = _generate_section(llm, llm_cache, modules_title, modules_context, language)
        toc_lines = "\n".join(
            [
                f"- [{Path(p).with_suffix('').as_posix()}]({Path(p).as_posix()[len('modules/'):] if p.startswith('modules/') else p})"
                for p in sorted(module_nav_paths)
            ]
        )
        docs_files["modules/index.md"] = f"# {modules_title}\n\n{intro}\n\n## Список модулей\n\n{toc_lines}\n"
        regenerated_sections.append(modules_title)
        docs_files.update(module_pages)

    # Project configs (detailed summaries -> per-config pages + index)
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
        docs_files["configs/index.md"] = f"# {configs_title}\n\n{_render_project_configs_index(config_nav_paths)}"
        regenerated_sections.append(configs_title)
        docs_files.update(config_pages)

    if executor:
        for future in as_completed(section_futures):
            out_path, title = section_futures[future]
            content = future.result()
            docs_files[out_path] = f"# {title}\n\n{content}\n"
            regenerated_sections.append(title)
        executor.shutdown(wait=True)

    # Remove stale config docs if domain no longer present
    configs_dir = docs_dir / "configs"
    if configs_dir.exists():
        for domain, title in DOMAIN_TITLES.items():
            if domain not in domain_contexts:
                stale_path = configs_dir / f"{domain}.md"
                if stale_path.exists():
                    stale_path.unlink()

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

    # Docs index for navigation
    docs_index = _build_docs_index(output_root, docs_dir, docs_files, file_map, module_pages, config_pages)
    docs_files["_index.json"] = json.dumps(docs_index, ensure_ascii=False, indent=2) + "\n"

    write_docs_files(docs_dir, docs_files)

    if write_readme:
        print("[ai-docs] write README")
        readme_path = output_root / "README.md"
        if readme_path.exists() and not force:
            print("[ai-docs] skip README: already exists (use --force to overwrite)")
        else:
            readme = _generate_readme(llm, llm_cache, output_root.name, overview_context, language)
            readme_path.write_text(readme + "\n", encoding="utf-8")

    # Remove orphan docs (keep .ai-docs/plans).
    # Only cleanup when actual source changes occurred.
    has_changes = bool(added or modified or deleted)
    if docs_dir.exists() and docs_files and has_changes:
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
    elif docs_dir.exists():
        print("[ai-docs] cleanup docs: skipped (no source changes)")

    if write_mkdocs:
        print("[ai-docs] mkdocs: build")
        mkdocs_yaml = build_mkdocs_yaml(
            site_name=output_root.name,
            sections=SECTION_TITLES,
            configs=configs_written,
            has_modules=bool(module_summaries),
            module_nav_paths=module_nav_paths if module_summaries else None,
            project_config_nav_paths=config_nav_paths if config_nav_paths else None,
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

    if errors:
        print("[ai-docs] errors summary:")
        for item in errors:
            print(f"[ai-docs] error: {item}")
