import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Union

import tomli

from .utils import read_text_file, sha256_text


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

NavItem = Union[str, Tuple[str, str]]


def is_test_path(path: str) -> bool:
    parts = Path(path).parts
    if any(part in {"test", "tests", "__tests__"} for part in parts):
        return True
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")


def _doc_path(base_dir: Path, source_path: str) -> str:
    source = Path(source_path)
    parent_parts = [
        f"__dot__{part[1:].replace('.', '__')}" if part.startswith(".") else part
        for part in source.parts[:-1]
    ]
    encoded_name = source.name.replace(".", "__")
    suffix = sha256_text(source_path)[:12]
    return (base_dir.joinpath(*parent_parts) / f"{encoded_name}_{suffix}.md").as_posix()


def module_doc_path(source_path: str) -> str:
    return _doc_path(Path("modules"), source_path)


def config_doc_path(source_path: str) -> str:
    return _doc_path(Path("configs/files"), source_path)


def nav_item_doc_path(item: NavItem) -> str:
    if isinstance(item, tuple):
        return item[0]
    return item


def _strip_hash_suffix(name: str) -> str:
    marker_at = len(name) - 13
    if marker_at <= 0 or name[marker_at] != "_":
        return name
    suffix = name[marker_at + 1 :]
    if len(suffix) == 12 and all(c in "0123456789abcdef" for c in suffix):
        return name[:marker_at]
    return name


def _decode_generated_segment(segment: str) -> str:
    if segment.startswith("__dot__"):
        return "." + segment[len("__dot__") :].replace("__", ".")
    return segment


def nav_item_label_path(item: NavItem, strip_prefix: str = "") -> str:
    if isinstance(item, tuple):
        return Path(item[1]).as_posix()
    rel = Path(item).as_posix()
    if strip_prefix and rel.startswith(strip_prefix):
        rel = rel[len(strip_prefix) :]
    parts = [_decode_generated_segment(part) for part in rel.split("/")]
    if not parts:
        return rel
    last = _strip_hash_suffix(Path(parts[-1]).with_suffix("").name)
    sep = last.rfind("__")
    if sep != -1 and sep + 2 < len(last):
        base = last[:sep]
        ext = last[sep + 2 :]
        parts[-1] = f"{base}.{ext}"
    else:
        parts[-1] = last
    return "/".join(parts)


def collect_dependencies(files: Dict[str, Dict]) -> List[str]:
    deps: List[str] = []
    for path, meta in files.items():
        if path.endswith("pyproject.toml"):
            data = tomli.loads(meta["content"])
            project_deps = data.get("project", {}).get("dependencies", [])
            if isinstance(project_deps, list):
                deps.extend(str(dep) for dep in project_deps)
            optional_deps = data.get("project", {}).get("optional-dependencies", {})
            if isinstance(optional_deps, dict):
                for extra, values in optional_deps.items():
                    if isinstance(values, list):
                        deps.extend(f"{dep} [{extra}]" for dep in values)
            deps_map = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            if isinstance(deps_map, dict):
                deps.extend([f"{k} {v}" for k, v in deps_map.items()])
        if path.endswith("requirements.txt"):
            lines = [line.strip() for line in meta["content"].splitlines() if line.strip() and not line.strip().startswith("#")]
            deps.extend(lines)
        if path.endswith("package.json"):
            data = json.loads(meta["content"])
            for section in ("dependencies", "devDependencies"):
                for k, v in data.get(section, {}).items():
                    deps.append(f"{k} {v}")
    return sorted(set(deps))


def collect_test_info(files: Dict[str, Dict]) -> Tuple[List[str], List[str]]:
    test_paths = sorted([path for path in files if is_test_path(path)])
    commands: List[str] = []
    for path, meta in files.items():
        if path.endswith("pyproject.toml"):
            data = tomli.loads(meta["content"])
            scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
            if scripts:
                commands.append("poetry run pytest")
            project_deps = data.get("project", {}).get("dependencies", [])
            optional_deps = data.get("project", {}).get("optional-dependencies", {})
            all_deps = [str(dep).lower() for dep in project_deps if isinstance(dep, str)]
            if isinstance(optional_deps, dict):
                for values in optional_deps.values():
                    if isinstance(values, list):
                        all_deps.extend(str(dep).lower() for dep in values if isinstance(dep, str))
            if test_paths and any(dep == "pytest" or dep.startswith("pytest") for dep in all_deps):
                commands.append("pytest -q")
        if path.endswith("setup.cfg"):
            commands.append("pytest")
        if path.endswith("tox.ini"):
            commands.append("tox")
        if path.endswith("package.json"):
            data = json.loads(meta.get("content", ""))
            scripts = data.get("scripts", {})
            if "test" in scripts:
                commands.append("npm test")

    return test_paths, sorted(set(commands))


def render_testing_section(test_paths: List[str], commands: List[str]) -> str:
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


def render_project_configs_index(config_nav_paths: List[NavItem]) -> str:
    if not config_nav_paths:
        return "Конфигурационные файлы не обнаружены."
    toc_lines = "\n".join(_format_config_toc_line(item) for item in _sort_nav_items(config_nav_paths))
    return f"## Файлы конфигурации\n\n{toc_lines}\n"


def _format_config_toc_line(item: NavItem) -> str:
    href = nav_item_doc_path(item)
    if href.startswith("configs/"):
        href = href[len("configs/") :]
    return f"- [{nav_item_label_path(item)}]({href})"


def _sort_nav_items(items: List[NavItem]) -> List[NavItem]:
    return sorted(items, key=lambda value: nav_item_label_path(value).lower())


def strip_duplicate_heading(content: str, title: str) -> str:
    lines = content.splitlines()
    if not lines:
        return content
    first = lines[0].strip()
    if first.startswith("#") and first.lstrip("#").strip().lower() == title.strip().lower():
        return "\n".join(lines[1:]).lstrip()
    return content


def first_paragraph(text: str) -> str:
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


def get_cached_text(meta: Dict[str, object], path_key: str, text_key: str) -> str:
    text = meta.get(text_key)
    if isinstance(text, str) and text:
        return text
    path = meta.get(path_key)
    if not isinstance(path, str) or not path:
        return ""
    text = read_text_file(Path(path))
    meta[text_key] = text
    return text


def build_docs_index(
    docs_dir: Path,
    docs_files: Dict[str, str],
    file_map: Dict[str, Dict],
    section_titles: Dict[str, str],
) -> Dict[str, object]:
    existing_files: Set[str] = set()
    if docs_dir.exists():
        for path in docs_dir.rglob("*.md"):
            try:
                existing_files.add(path.relative_to(docs_dir).as_posix())
            except Exception:
                continue
    sections = []
    for key, title in section_titles.items():
        path = f"{key}.md"
        if path in docs_files or path in existing_files:
            sections.append({"id": key, "title": title, "path": path})
    if "configs/index.md" in docs_files or "configs/index.md" in existing_files:
        sections.append({"id": "configs", "title": "Конфигурация проекта", "path": "configs/index.md"})

    modules = []
    for path, meta in file_map.items():
        if is_test_path(path):
            continue
        summary_path = meta.get("module_summary_path")
        if not summary_path:
            continue
        module_rel_str = module_doc_path(path)
        if module_rel_str not in docs_files and module_rel_str not in existing_files:
            continue
        summary_text = get_cached_text(meta, "module_summary_path", "module_summary_text")
        modules.append(
            {
                "name": Path(path).with_suffix("").as_posix(),
                "path": module_rel_str,
                "source_path": path,
                "summary": first_paragraph(summary_text),
            }
        )

    configs = []
    for path, meta in file_map.items():
        if meta.get("type") != "config":
            continue
        summary_path = meta.get("config_summary_path")
        if not summary_path:
            continue
        config_rel_str = config_doc_path(path)
        if config_rel_str not in docs_files and config_rel_str not in existing_files:
            continue
        summary_text = get_cached_text(meta, "config_summary_path", "config_summary_text")
        configs.append(
            {
                "name": Path(path).as_posix(),
                "path": config_rel_str,
                "source_path": path,
                "summary": first_paragraph(summary_text),
            }
        )

    return {
        "sections": sections,
        "modules": modules,
        "configs": configs,
        "files": sorted(set(docs_files.keys()) | existing_files | {"_index.json"}),
    }
