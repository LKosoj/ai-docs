from pathlib import Path
from typing import Dict, List

import yaml


def build_mkdocs_yaml(site_name: str, sections: Dict[str, str], configs: Dict[str, str], local_site: bool = False) -> str:
    nav = [
        {"Главная": "index.md"},
    ]
    if "architecture" in sections:
        nav.append({"Архитектура": "architecture.md"})
    if "runtime" in sections:
        nav.append({"Запуск": "runtime.md"})
    if "dependencies" in sections:
        nav.append({"Зависимости": "dependencies.md"})
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

    nav.append({"Изменения": "changes.md"})

    data = {
        "site_name": site_name,
        "docs_dir": ".ai-docs",
        "site_dir": "ai_docs_site",
        "nav": nav,
    }
    if local_site:
        data["site_url"] = ""
        data["use_directory_urls"] = False
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def write_docs_files(docs_dir: Path, files: Dict[str, str]) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files.items():
        out_path = docs_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
