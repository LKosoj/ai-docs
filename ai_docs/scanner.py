import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pathspec

from .domain import classify_type, detect_domains, is_infra
from .utils import is_binary_file, is_url, read_text_file, to_posix


DEFAULT_INCLUDE_PATTERNS = {
    "*.py", "*.pyi", "*.pyx", "*.js", "*.jsx", "*.ts", "*.tsx", "*.go", "*.java",
    "*.c", "*.cc", "*.cpp", "*.h", "*.hpp", "*.rs", "*.rb", "*.php", "*.cs",
    "*.kt", "*.kts", "*.swift", "*.m", "*.mm",
    "*.md", "*.rst", "*.adoc", "*.txt",
    "*.yml", "*.yaml", "*.json", "*.toml", "*.ini", "*.cfg", "*.conf", "*.env",
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
    "**/.ai_docs_cache/*", "**/site/*", "**/ai_docs_site/*",
    "mkdocs.yml", "**/mkdocs.yml", "mkdocs_yml.md", "**/mkdocs_yml.md",
}


class ScanResult:
    def __init__(self, root: Path, files: List[Dict], source: str, repo_name: str):
        self.root = root
        self.files = files
        self.source = source
        self.repo_name = repo_name


def _load_gitignore(root: Path) -> Optional[pathspec.PathSpec]:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return None
    patterns = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def _should_include(rel_path: str, include: Optional[Set[str]], exclude: Optional[Set[str]], gitignore: Optional[pathspec.PathSpec]) -> bool:
    if gitignore and gitignore.match_file(rel_path):
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
    gitignore = _load_gitignore(root)

    for dirpath, dirnames, filenames in os.walk(root):
        # Avoid .git directory traversal
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for filename in filenames:
            abs_path = Path(dirpath) / filename
            rel_path = abs_path.relative_to(root)
            rel_path_str = to_posix(rel_path)

            if not _should_include(rel_path_str, include, exclude, gitignore):
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
    include = include or DEFAULT_INCLUDE_PATTERNS
    exclude = exclude or DEFAULT_EXCLUDE_PATTERNS

    if is_url(source):
        root, repo_name = _clone_repo(source)
        files = _scan_directory(root, include, exclude, max_size)
        return ScanResult(root=root, files=files, source=source, repo_name=repo_name)

    root = Path(source).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Source path not found: {root}")
    files = _scan_directory(root, include, exclude, max_size)
    return ScanResult(root=root, files=files, source=str(root), repo_name=root.name)
