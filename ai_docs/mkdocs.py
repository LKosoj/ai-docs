from pathlib import Path
from typing import Dict, List

import yaml


class _YamlPythonName(str):
    pass


class _YamlSafeDumper(yaml.SafeDumper):
    pass


def _python_name_representer(dumper: yaml.Dumper, data: _YamlPythonName) -> yaml.nodes.ScalarNode:
    return dumper.represent_scalar(f"tag:yaml.org,2002:python/name:{data}", "")


_YamlSafeDumper.add_representer(_YamlPythonName, _python_name_representer)


def build_mkdocs_yaml(
    site_name: str,
    sections: Dict[str, str],
    configs: Dict[str, str],
    local_site: bool = False,
    has_modules: bool = False,
    module_nav_paths: List[str] | None = None,
    project_config_nav_paths: List[str] | None = None,
) -> str:
    nav = [
        {"Главная": "index.md"},
    ]
    if "architecture" in sections:
        nav.append({"Архитектура": "architecture.md"})
    if "runtime" in sections:
        nav.append({"Запуск": "runtime.md"})
    if "dependencies" in sections:
        nav.append({"Зависимости": "dependencies.md"})
    if "testing" in sections:
        nav.append({"Тестирование": "testing.md"})
    if "conventions" in sections:
        nav.append({"Соглашения": "conventions.md"})
    if "glossary" in sections:
        nav.append({"Глоссарий": "glossary.md"})

    if configs:
        cfg_nav: List[Dict[str, str]] = []
        for key, filename in configs.items():
            title = {
                "kubernetes": "Kubernetes",
                "helm": "Helm",
                "terraform": "Terraform",
                "ansible": "Ansible",
                "docker": "Docker",
                "ci": "CI/CD",
            }.get(key, key)
            cfg_nav.append({title: f"configs/{filename}"})
        nav.append({"Конфиги": cfg_nav})

    if project_config_nav_paths:
        project_cfg_nav: List[Dict[str, object]] = [{"Обзор": "configs/index.md"}]
        project_cfg_nav.extend(_build_tree_nav(project_config_nav_paths, "configs/files/"))
        nav.append({"Конфигурация проекта": project_cfg_nav})

    if has_modules:
        modules_nav: List[Dict[str, object]] = [{"Обзор": "modules/index.md"}]
        if module_nav_paths:
            modules_nav.extend(_build_tree_nav(module_nav_paths, "modules/"))
        nav.append({"Модули": modules_nav})

    nav.append({"Изменения": "changes.md"})

    data = {
        "site_name": site_name,
        "docs_dir": ".ai-docs",
        "site_dir": "ai_docs_site",
        "plugins": [
            "search",
            {"mermaid2": {"javascript": "https://unpkg.com/mermaid@10.4.0/dist/mermaid.esm.min.mjs"}},
        ],
        "markdown_extensions": [
            "tables",
            "sane_lists",
            "attr_list",
            "def_list",
            "footnotes",
            "admonition",
            "fenced_code",
            {
                "pymdownx.superfences": {
                    "custom_fences": [
                        {
                            "name": "mermaid",
                            "class": "mermaid",
                            "format": _YamlPythonName("mermaid2.fence_mermaid"),
                        }
                    ]
                }
            },
        ],
        "nav": nav,
    }
    if local_site:
        data["site_url"] = ""
        data["use_directory_urls"] = False
    return yaml.dump(data, allow_unicode=True, sort_keys=False, Dumper=_YamlSafeDumper)


def _build_tree_nav(paths: List[str], strip_prefix: str) -> List[Dict[str, object]]:
    tree: Dict[str, object] = {}

    for rel_path in paths:
        rel = Path(rel_path).as_posix()
        if rel.startswith(strip_prefix):
            rel = rel[len(strip_prefix) :]
        parts = rel.split("/")
        if parts:
            last = Path(parts[-1]).with_suffix("").name
            sep = last.rfind("__")
            if sep != -1 and sep + 2 < len(last):
                base = last[:sep]
                ext = last[sep + 2 :]
                parts[-1] = f"{base}.{ext}"
            else:
                parts[-1] = last
        _insert_nav_node(tree, parts, rel_path)

    return _tree_to_nav(tree)


def _insert_nav_node(tree: Dict[str, object], parts: List[str], rel_path: str) -> None:
    key = parts[0]
    if len(parts) == 1:
        tree[key] = rel_path
        return
    node = tree.get(key)
    if not isinstance(node, dict):
        node = {}
        tree[key] = node
    _insert_nav_node(node, parts[1:], rel_path)


def _tree_to_nav(tree: Dict[str, object]) -> List[Dict[str, object]]:
    nav: List[Dict[str, object]] = []
    for key in sorted(tree.keys(), key=lambda k: (not isinstance(tree[k], dict), k.lower())):
        value = tree[key]
        if isinstance(value, dict):
            label = key if key.startswith("/") else f"/{key}"
            nav.append({label: _tree_to_nav(value)})
        else:
            nav.append({key: value})
    return nav


def write_docs_files(docs_dir: Path, files: Dict[str, str]) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files.items():
        out_path = docs_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
