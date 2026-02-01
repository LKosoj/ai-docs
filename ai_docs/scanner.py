import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pathspec
import yaml

from .domain import (
    CODE_EXTENSION_DESCRIPTIONS,
    CONFIG_EXTENSION_DESCRIPTIONS,
    DOC_EXTENSION_DESCRIPTIONS,
    classify_type,
    detect_domains,
    is_infra,
)
from .utils import is_binary_file, is_url, read_text_file, to_posix


FIXED_INCLUDE_PATTERNS = {
    "*.tf", "*.tfvars",
    "Dockerfile*", "docker-compose*.yml", "docker-compose*.yaml", "compose.yml", "compose.yaml",
    "Jenkinsfile", ".gitlab-ci.yml", "azure-pipelines.yml",
    "requirements.txt", "pyproject.toml", "package.json", "package-lock.json",
}

DEFAULT_EXCLUDE_PATTERNS = {
    ".git/*", "**/.git/*",
    ".venv/*", ".venv/**", "**/.venv/*", "**/.venv/**",
    "venv/*", "venv/**", "**/venv/*", "**/venv/**",
    "**/node_modules/*",
    "**/dist/*", "**/build/*",
    "**/.idea/*", "**/.vscode/*", "**/__pycache__/*",
    "**/.pytest_cache/*", "**/.mypy_cache/*",
    "**/.ai_docs_cache/*", "**/ai_docs_site/*",
    ".ai-docs/*", ".ai-docs/**", "**/.ai-docs/*", "**/.ai-docs/**",
    ".github/*", ".github/**", "**/.github/*", "**/.github/**",
    "mkdocs.yml", "**/mkdocs.yml", "mkdocs_yml.md", "**/mkdocs_yml.md",
}


class ScanResult:
    def __init__(self, root: Path, files: List[Dict], source: str, repo_name: str):
        self.root = root
        self.files = files
        self.source = source
        self.repo_name = repo_name


def _normalize_extensions(raw: Dict, defaults: Dict[str, str]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key, value in raw.items():
        ext = str(key).strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        desc = value if isinstance(value, str) and value.strip() else defaults.get(ext, "")
        normalized[ext] = desc
    return normalized or defaults.copy()


def _load_extension_config(root: Path) -> Dict[str, Dict[str, str]]:
    config_path = root / ".ai-docs.yaml"
    defaults = {
        "code_extensions": CODE_EXTENSION_DESCRIPTIONS,
        "doc_extensions": DOC_EXTENSION_DESCRIPTIONS,
        "config_extensions": CONFIG_EXTENSION_DESCRIPTIONS,
    }

    if not config_path.exists():
        payload = {
            "code_extensions": defaults["code_extensions"],
            "doc_extensions": defaults["doc_extensions"],
            "config_extensions": defaults["config_extensions"],
        }
        config_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return {key: value.copy() for key, value in defaults.items()}

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8", errors="ignore")) or {}
    except yaml.YAMLError:
        return {key: value.copy() for key, value in defaults.items()}

    if not isinstance(raw, dict):
        return {key: value.copy() for key, value in defaults.items()}

    code_raw = raw.get("code_extensions") or {}
    doc_raw = raw.get("doc_extensions") or {}
    config_raw = raw.get("config_extensions") or {}

    if not isinstance(code_raw, dict):
        code_raw = {}
    if not isinstance(doc_raw, dict):
        doc_raw = {}
    if not isinstance(config_raw, dict):
        config_raw = {}

    return {
        "code_extensions": _normalize_extensions(code_raw, defaults["code_extensions"]),
        "doc_extensions": _normalize_extensions(doc_raw, defaults["doc_extensions"]),
        "config_extensions": _normalize_extensions(config_raw, defaults["config_extensions"]),
    }


def _build_default_include_patterns(extension_config: Dict[str, Dict[str, str]]) -> Set[str]:
    extensions: Set[str] = set()
    for key in ("code_extensions", "doc_extensions", "config_extensions"):
        extensions.update(extension_config.get(key, {}).keys())
    return {f"*{ext}" for ext in extensions} | FIXED_INCLUDE_PATTERNS


def _load_ignore_specs(root: Path) -> List[pathspec.PathSpec]:
    specs: List[pathspec.PathSpec] = []
    for name in (".gitignore", ".build_ignore"):
        ignore_file = root / name
        if not ignore_file.exists():
            continue
        patterns = ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        specs.append(pathspec.PathSpec.from_lines("gitignore", patterns))
    return specs


def _should_include(rel_path: str, include: Optional[Set[str]], exclude: Optional[Set[str]], ignore_specs: List[pathspec.PathSpec]) -> bool:
    for spec in ignore_specs:
        if spec.match_file(rel_path):
            return False
    if exclude:
        for pattern in exclude:
            if pathspec.PathSpec.from_lines("gitignore", [pattern]).match_file(rel_path):
                return False
    if not include:
        return True
    for pattern in include:
        if pathspec.PathSpec.from_lines("gitignore", [pattern]).match_file(rel_path):
            return True
    return False


def _scan_directory(root: Path, include: Optional[Set[str]], exclude: Optional[Set[str]], max_size: int) -> List[Dict]:
    files: List[Dict] = []
    ignore_specs = _load_ignore_specs(root)

    for dirpath, dirnames, filenames in os.walk(root):
        # Avoid .git directory traversal
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for filename in filenames:
            abs_path = Path(dirpath) / filename
            rel_path = abs_path.relative_to(root)
            rel_path_str = to_posix(rel_path)

            if not _should_include(rel_path_str, include, exclude, ignore_specs):
                continue

            if abs_path.is_symlink():
                continue

            try:
                size = abs_path.stat().st_size
            except OSError:
                continue

            if max_size and size > max_size:
                continue

            if is_binary_file(abs_path):
                continue

            content = read_text_file(abs_path)
            content_snippet = content[:4000]
            file_type = classify_type(abs_path)
            domains = detect_domains(abs_path, content_snippet)
            if is_infra(domains):
                file_type = "infra"

            files.append(
                {
                    "path": rel_path_str,
                    "abs_path": abs_path,
                    "size": size,
                    "content": content,
                    "type": file_type,
                    "domains": sorted(domains),
                }
            )

    return files


def _clone_repo(repo_url: str) -> Tuple[Path, str]:
    tmpdir = Path(tempfile.mkdtemp(prefix="ai_docs_"))
    try:
        subprocess.check_call(["git", "clone", "--depth", "1", repo_url, str(tmpdir)])
    except Exception as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"Failed to clone repo: {exc}")
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    return tmpdir, repo_name


def scan_source(source: str, include: Optional[Set[str]] = None, exclude: Optional[Set[str]] = None, max_size: int = 200_000) -> ScanResult:
    exclude = exclude or DEFAULT_EXCLUDE_PATTERNS

    if is_url(source):
        root, repo_name = _clone_repo(source)
        include = include or _build_default_include_patterns(_load_extension_config(root))
        files = _scan_directory(root, include, exclude, max_size)
        return ScanResult(root=root, files=files, source=source, repo_name=repo_name)

    root = Path(source).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Source path not found: {root}")
    include = include or _build_default_include_patterns(_load_extension_config(root))
    files = _scan_directory(root, include, exclude, max_size)
    return ScanResult(root=root, files=files, source=str(root), repo_name=root.name)
