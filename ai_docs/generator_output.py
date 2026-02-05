from pathlib import Path
from typing import Dict, List
import time

from .generator_shared import DOMAIN_TITLES, SECTION_TITLES, build_docs_index
from .mkdocs import build_mkdocs_yaml, write_docs_files


def add_mermaid_asset(docs_files: Dict[str, str]) -> None:
    mermaid_asset = Path(__file__).parent / "assets" / "mermaid.min.js"
    if mermaid_asset.exists():
        docs_files["js/mermaid.min.js"] = mermaid_asset.read_text(encoding="utf-8")
    else:
        print(f"[ai-docs] warning: mermaid asset not found: {mermaid_asset}")


def write_docs(
    output_root: Path,
    docs_dir: Path,
    docs_files: Dict[str, str],
    file_map: Dict[str, Dict],
    module_pages: Dict[str, str],
    config_pages: Dict[str, str],
    has_changes: bool,
) -> None:
    docs_index = build_docs_index(docs_dir, docs_files, file_map, SECTION_TITLES)
    docs_files["_index.json"] = __serialize_index(docs_index)
    add_mermaid_asset(docs_files)
    write_docs_files(docs_dir, docs_files)

    if docs_dir.exists() and docs_files and has_changes:
        print("[ai-docs] cleanup docs: removing orphan files")
        keep_files = {docs_dir / rel for rel in docs_files.keys()}
        keep_files.add(docs_dir / "index.md")
        keep_files.add(docs_dir / "overview.md")
        keep_files.add(docs_dir / "changes.md")
        keep_files.add(docs_dir / "modules" / "index.md")
        keep_files.add(docs_dir / "configs" / "index.md")
        for key in SECTION_TITLES.keys():
            keep_files.add(docs_dir / f"{key}.md")
        for domain in DOMAIN_TITLES.keys():
            keep_files.add(docs_dir / "configs" / f"{domain}.md")
        for path in (docs_dir / "modules").glob("page-*.md"):
            keep_files.add(path)
        for path in (docs_dir / "configs").glob("page-*.md"):
            keep_files.add(path)
        keep_dirs = {docs_dir / "plans"}
        to_remove: List[Path] = []
        for path in docs_dir.rglob("*"):
            if path.is_dir():
                continue
            if any(str(path).startswith(str(keep_dir)) for keep_dir in keep_dirs):
                continue
            if path in keep_files:
                continue
            to_remove.append(path)
        total = len(to_remove)
        if total:
            done = 0
            start = time.time()
            log_every = 5
            for path in to_remove:
                path.unlink()
                done += 1
                if done % log_every == 0 or done == total:
                    elapsed = int(time.time() - start)
                    print(f"[ai-docs] cleanup docs progress: {done}/{total} ({elapsed}s)")
    elif docs_dir.exists():
        print("[ai-docs] cleanup docs: skipped (no source changes)")


def write_readme(output_root: Path, readme: str, force: bool) -> None:
    readme_path = output_root / "README.md"
    if readme_path.exists() and not force:
        print("[ai-docs] skip README: already exists (use --force to overwrite)")
    else:
        readme_path.write_text(readme + "\n", encoding="utf-8")


def build_mkdocs(
    output_root: Path,
    module_nav_paths: List[str],
    config_nav_paths: List[str],
    configs_written: Dict[str, str],
    write_mkdocs: bool,
    local_site: bool,
) -> None:
    if not write_mkdocs:
        return
    print("[ai-docs] mkdocs: build")
    mkdocs_yaml = build_mkdocs_yaml(
        site_name=output_root.name,
        sections=SECTION_TITLES,
        configs=configs_written,
        has_modules=bool(module_nav_paths),
        module_nav_paths=module_nav_paths if module_nav_paths else None,
        project_config_nav_paths=config_nav_paths if config_nav_paths else None,
        local_site=local_site,
    )
    (output_root / "mkdocs.yml").write_text(mkdocs_yaml, encoding="utf-8")
    import shutil
    import subprocess

    venv_mkdocs = output_root / ".venv" / "bin" / "mkdocs"
    venv_python = output_root / ".venv" / "bin" / "python"
    if venv_mkdocs.exists():
        cmd = [str(venv_mkdocs), "build", "-f", "mkdocs.yml"]
    elif venv_python.exists():
        cmd = [str(venv_python), "-m", "mkdocs", "build", "-f", "mkdocs.yml"]
    else:
        mkdocs_bin = shutil.which("mkdocs")
        if not mkdocs_bin:
            raise RuntimeError("mkdocs is not installed or not on PATH")
        cmd = [mkdocs_bin, "build", "-f", "mkdocs.yml"]
    subprocess.check_call(cmd, cwd=output_root)
    _postprocess_mermaid_html(output_root / "ai_docs_site")


def _postprocess_mermaid_html(site_dir: Path) -> None:
    if not site_dir.exists():
        return
    html_paths = list(site_dir.rglob("*.html"))
    total = len(html_paths)
    done = 0
    start = time.time()
    log_every = 5
    for html_path in html_paths:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
        if "<div class=\"mermaid\"" not in text:
            continue
        text = text.replace("&gt;", ">")
        html_path.write_text(text, encoding="utf-8")
        done += 1
        if done % log_every == 0 or done == total:
            elapsed = int(time.time() - start)
            print(f"[ai-docs] mkdocs postprocess progress: {done}/{total} ({elapsed}s)")


def __serialize_index(index: Dict[str, object]) -> str:
    import json
    from datetime import datetime

    payload = {
        **index,
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
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
