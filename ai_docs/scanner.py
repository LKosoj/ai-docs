import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import pathspec

from .config import load_extension_config
from .domain import (
    classify_type,
    detect_domains,
    is_infra,
)
from .domain_rules import (
    CODE_EXTENSION_DESCRIPTIONS,
    CONFIG_EXTENSION_DESCRIPTIONS,
    DOC_EXTENSION_DESCRIPTIONS,
    DEFAULT_EXCLUDE_PATTERNS,
    FIXED_INCLUDE_PATTERNS,
    PRUNABLE_DIR_NAMES,
    PRUNABLE_DIR_PATHS,
)
from .utils import is_binary_file, is_url, sha256_bytes, to_posix


PARALLEL_LOAD_THRESHOLD = 32


class ScanResult:
    def __init__(self, root: Path, files: List[Dict], source: str, repo_name: str):
        self.root = root
        self.files = files
        self.source = source
        self.repo_name = repo_name


def _load_extension_config(root: Path) -> Dict[str, object]:
    defaults = {
        "code_extensions": CODE_EXTENSION_DESCRIPTIONS,
        "doc_extensions": DOC_EXTENSION_DESCRIPTIONS,
        "config_extensions": CONFIG_EXTENSION_DESCRIPTIONS,
    }
    return load_extension_config(root, defaults)


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
        raw = abs_path.read_bytes()
        decode_error = None
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            decode_error = f"utf-8 decode error at byte {exc.start}: {exc.reason}; invalid bytes ignored"
            content = raw.decode("utf-8", errors="ignore")
    except OSError:
        return None

    content_snippet = content[:4000]
    file_type = classify_type(abs_path)
    domains = detect_domains(abs_path, content_snippet)
    if file_type != "ci" and is_infra(domains):
        file_type = "infra"

    record = {
        "path": rel_path_str,
        "abs_path": abs_path,
        "size": size,
        "hash": sha256_bytes(raw),
        "content": content,
        "type": file_type,
        "domains": sorted(domains),
    }
    if decode_error:
        record["decode_error"] = decode_error
    return record


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


def path_in_scan_scope(
    root: Path,
    rel_path: str,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
) -> bool:
    extension_config = _load_extension_config(root)
    effective_include = include or _build_default_include_patterns(extension_config)
    effective_exclude = set(exclude or DEFAULT_EXCLUDE_PATTERNS)
    effective_exclude |= set(extension_config.get("exclude", set()))
    include_spec = _compile_pathspec(effective_include)
    exclude_spec = _compile_pathspec(effective_exclude)
    ignore_specs = _load_ignore_specs(root)
    return _should_include(rel_path, include_spec, exclude_spec, ignore_specs)


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
