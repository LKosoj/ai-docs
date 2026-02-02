import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

import tomli

from .utils import read_text_file


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


def is_test_path(path: str) -> bool:
    parts = Path(path).parts
    if any(part in {"test", "tests", "__tests__"} for part in parts):
        return True
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")


def collect_dependencies(files: Dict[str, Dict]) -> List[str]:
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


def collect_test_info(files: Dict[str, Dict]) -> Tuple[List[str], List[str]]:
    test_paths = sorted([path for path in files if is_test_path(path)])
    commands: List[str] = []
    for path, meta in files.items():
        if path.endswith("pyproject.toml"):
            try:
                data = tomli.loads(meta["content"])
                scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
                if scripts:
                    commands.append("poetry run pytest")
            except Exception:
                continue
        if path.endswith("setup.cfg"):
            commands.append("pytest")
        if path.endswith("tox.ini"):
            commands.append("tox")
        if path.endswith("package.json"):
            try:
                data = json.loads(meta.get("content", ""))
                scripts = data.get("scripts", {})
                if "test" in scripts:
                    commands.append("npm test")
            except Exception:
                continue

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


def render_project_configs_index(config_nav_paths: List[str]) -> str:
    if not config_nav_paths:
        return "Конфигурационные файлы не обнаружены."
    toc_lines = "\n".join(
        [
            f"- [{Path(p).with_suffix('').as_posix()}]({Path(p).as_posix()[len('configs/'):] if p.startswith('configs/') else p})"
            for p in sorted(config_nav_paths)
        ]
    )
    return f"## Файлы конфигурации\n\n{toc_lines}\n"


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
        module_rel = Path("modules") / Path(path).with_suffix("")
        module_rel_str = module_rel.as_posix() + ".md"
        summary_text = read_text_file(Path(summary_path))
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
        config_rel = Path("configs/files") / Path(path)
        config_rel_str = config_rel.as_posix().replace(".", "__") + ".md"
        summary_text = read_text_file(Path(summary_path))
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
