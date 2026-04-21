import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

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
    "**/.ai_docs_cache/*", "**/.ai_docs_cache/**", ".ai_docs_cache/**", ".ai_docs_cache/*",
    "**/ai_docs_site/*", "**/ai_docs_site/**", "ai_docs_site/**", "ai_docs_site/*",
    ".ai-docs/*", ".ai-docs/**", "**/.ai-docs/*", "**/.ai-docs/**",
    ".github/*", ".github/**", "**/.github/*", "**/.github/**",
    "mkdocs.yml", "**/mkdocs.yml", "mkdocs_yml.md", "**/mkdocs_yml.md",
    ".ai-docs.yaml", "**/.ai-docs.yaml",
    "ai_docs/assets/*", "ai_docs/assets/**", "**/ai_docs/assets/*", "**/ai_docs/assets/**",
}

PRUNABLE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ai_docs_cache",
    "ai_docs_site",
    ".ai-docs",
    ".github",
}

PRUNABLE_DIR_PATHS = {
    "ai_docs/assets",
}

PARALLEL_LOAD_THRESHOLD = 32


class ScanResult:
    def __init__(self, root: Path, files: List[Dict], source: str, repo_name: str):
        self.root = root
        self.files = files
        self.source = source
        self.repo_name = repo_name


def _normalize_extensions(raw: object, defaults: Dict[str, str]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    if isinstance(raw, dict):
        items = raw.items()
        for key, value in items:
            ext = str(key).strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            desc = value if isinstance(value, str) and value.strip() else defaults.get(ext, "")
            normalized[ext] = desc
    elif isinstance(raw, list):
        for item in raw:
            ext = str(item).strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized[ext] = defaults.get(ext, "")
    return normalized or defaults.copy()


def _normalize_excludes(raw: object) -> Set[str]:
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def _load_extension_config(root: Path) -> Dict[str, object]:
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
        return {**{key: value.copy() for key, value in defaults.items()}, "exclude": set()}

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8", errors="ignore")) or {}
    except yaml.YAMLError:
        return {**{key: value.copy() for key, value in defaults.items()}, "exclude": set()}

    if not isinstance(raw, dict):
        return {**{key: value.copy() for key, value in defaults.items()}, "exclude": set()}

    code_raw = raw.get("code_extensions") or {}
    doc_raw = raw.get("doc_extensions") or {}
    config_raw = raw.get("config_extensions") or {}
    exclude_raw = raw.get("exclude") or []

    return {
        "code_extensions": _normalize_extensions(code_raw, defaults["code_extensions"]),
        "doc_extensions": _normalize_extensions(doc_raw, defaults["doc_extensions"]),
        "config_extensions": _normalize_extensions(config_raw, defaults["config_extensions"]),
        "exclude": _normalize_excludes(exclude_raw),
    }


def _build_default_include_patterns(extension_config: Dict[str, object]) -> Set[str]:
    extensions: Set[str] = set()
    for key in ("code_extensions", "doc_extensions", "config_extensions"):
        extensions.update(extension_config.get(key, {}).keys())
    return {f"*{ext}" for ext in extensions} | FIXED_INCLUDE_PATTERNS


def _compile_pathspec(patterns: Optional[Set[str]]) -> Optional[pathspec.PathSpec]:
    if not patterns:
        return None
    return pathspec.PathSpec.from_lines("gitignore", sorted(patterns))


def _load_ignore_specs(root: Path) -> List[pathspec.PathSpec]:
    specs: List[pathspec.PathSpec] = []
    for name in (".gitignore", ".build_ignore"):
        ignore_file = root / name
        if not ignore_file.exists():
            continue
        patterns = ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        specs.append(pathspec.PathSpec.from_lines("gitignore", patterns))
    return specs


def _matches_any_spec(rel_path: str, specs: Optional[pathspec.PathSpec]) -> bool:
    return bool(specs and specs.match_file(rel_path))


def _should_include(
    rel_path: str,
    include_spec: Optional[pathspec.PathSpec],
    exclude_spec: Optional[pathspec.PathSpec],
    ignore_specs: Sequence[pathspec.PathSpec],
) -> bool:
    for spec in ignore_specs:
        if spec.match_file(rel_path):
            return False
    if _matches_any_spec(rel_path, exclude_spec):
        return False
    if not include_spec:
        return True
    return _matches_any_spec(rel_path, include_spec)


def _should_prune_dir(
    rel_dir: str,
    exclude_spec: Optional[pathspec.PathSpec],
    ignore_specs: Sequence[pathspec.PathSpec],
) -> bool:
    dir_name = rel_dir.rsplit("/", 1)[-1]
    if dir_name in PRUNABLE_DIR_NAMES:
        return True
    if any(rel_dir == path or rel_dir.endswith(f"/{path}") for path in PRUNABLE_DIR_PATHS):
        return True
    if _matches_any_spec(rel_dir, exclude_spec):
        return True
    for spec in ignore_specs:
        if spec.match_file(rel_dir):
            return True
    return False


def _load_file_record(task: Tuple[str, str, int]) -> Optional[Dict]:
    abs_path_str, rel_path_str, max_size = task
    abs_path = Path(abs_path_str)

    try:
        if abs_path.is_symlink():
            return None
        size = abs_path.stat().st_size
        if max_size and size > max_size:
            return None
        if is_binary_file(abs_path):
            return None
        content = read_text_file(abs_path)
    except OSError:
        return None

    content_snippet = content[:4000]
    file_type = classify_type(abs_path)
    domains = detect_domains(abs_path, content_snippet)
    if is_infra(domains):
        file_type = "infra"

    return {
        "path": rel_path_str,
        "abs_path": abs_path,
        "size": size,
        "content": content,
        "type": file_type,
        "domains": sorted(domains),
    }


def _scan_directory(
    root: Path,
    include_spec: Optional[pathspec.PathSpec],
    exclude_spec: Optional[pathspec.PathSpec],
    max_size: int,
    workers: int,
) -> List[Dict]:
    files: List[Dict] = []
    ignore_specs = _load_ignore_specs(root)
    tasks: List[Tuple[str, str, int]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not _should_prune_dir(
                to_posix((current_dir / dirname).relative_to(root)),
                exclude_spec,
                ignore_specs,
            )
        ]
        for filename in filenames:
            abs_path = current_dir / filename
            rel_path_str = to_posix(abs_path.relative_to(root))
            if not _should_include(rel_path_str, include_spec, exclude_spec, ignore_specs):
                continue
            tasks.append((str(abs_path), rel_path_str, max_size))

    if workers > 1 and len(tasks) >= PARALLEL_LOAD_THRESHOLD:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for record in executor.map(_load_file_record, tasks):
                if record is not None:
                    files.append(record)
        return files

    for task in tasks:
        record = _load_file_record(task)
        if record is not None:
            files.append(record)
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


def scan_source(
    source: str,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
    max_size: int = 200_000,
    workers: int = 5,
) -> ScanResult:
    exclude = set(exclude or DEFAULT_EXCLUDE_PATTERNS)

    if is_url(source):
        root, repo_name = _clone_repo(source)
        extension_config = _load_extension_config(root)
        include = include or _build_default_include_patterns(extension_config)
        exclude = set(exclude) | set(extension_config.get("exclude", set()))
        include_spec = _compile_pathspec(include)
        exclude_spec = _compile_pathspec(exclude)
        files = _scan_directory(root, include_spec, exclude_spec, max_size, workers)
        return ScanResult(root=root, files=files, source=source, repo_name=repo_name)

    root = Path(source).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Source path not found: {root}")
    extension_config = _load_extension_config(root)
    include = include or _build_default_include_patterns(extension_config)
    exclude = set(exclude) | set(extension_config.get("exclude", set()))
    include_spec = _compile_pathspec(include)
    exclude_spec = _compile_pathspec(exclude)
    files = _scan_directory(root, include_spec, exclude_spec, max_size, workers)
    return ScanResult(root=root, files=files, source=str(root), repo_name=root.name)
