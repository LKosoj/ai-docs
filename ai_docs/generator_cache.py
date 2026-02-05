from pathlib import Path
from typing import Dict, List, Tuple

from .cache import CacheManager
from .generator_shared import is_test_path
from .utils import ensure_dir, sha256_text


def init_cache(cache_dir: Path, use_cache: bool):
    cache = CacheManager(cache_dir)
    llm_cache = cache.load_llm_cache() if use_cache else None
    index_data = cache.load_index()
    prev_files = index_data.get("files", {})
    return cache, llm_cache, index_data, prev_files


def build_file_map(files: List[Dict]) -> Dict[str, Dict]:
    file_map: Dict[str, Dict] = {}
    for f in files:
        file_map[f["path"]] = {
            "hash": sha256_text(f["content"]),
            "size": f["size"],
            "type": f["type"],
            "domains": f["domains"],
            "content": f["content"],
        }
    return file_map


def diff_files(cache: CacheManager, file_map: Dict[str, Dict]):
    return cache.diff_files(file_map)


def ensure_summary_dirs(cache_dir: Path):
    summaries_dir = cache_dir / "intermediate" / "files"
    module_summaries_dir = cache_dir / "intermediate" / "modules"
    config_summaries_dir = cache_dir / "intermediate" / "configs"
    ensure_dir(summaries_dir)
    ensure_dir(module_summaries_dir)
    ensure_dir(config_summaries_dir)
    return summaries_dir, module_summaries_dir, config_summaries_dir


def save_cache_snapshot(
    cache: CacheManager,
    file_map: Dict[str, Dict],
    index_data: Dict,
    llm_cache: Dict[str, str],
    use_cache: bool,
) -> None:
    snapshot = {
        "files": {path: {k: v for k, v in meta.items() if k != "content"} for path, meta in file_map.items()},
        "sections": index_data.get("sections", {}),
    }
    cache.save_index(snapshot)
    if use_cache and llm_cache is not None:
        cache.save_llm_cache(llm_cache)


def carry_unchanged_summaries(
    unchanged: Dict[str, Dict],
    prev_files: Dict[str, Dict],
) -> Tuple[List[Tuple[str, Dict]], List[Tuple[str, Dict]], List[Tuple[str, Dict]]]:
    missing_summaries: List[Tuple[str, Dict]] = []
    missing_module_summaries: List[Tuple[str, Dict]] = []
    missing_config_summaries: List[Tuple[str, Dict]] = []
    for path, meta in unchanged.items():
        prev = prev_files.get(path, {})
        summary_path = prev.get("summary_path")
        if summary_path and Path(summary_path).exists():
            meta["summary_path"] = summary_path
        else:
            missing_summaries.append((path, meta))
        module_summary_path = prev.get("module_summary_path")
        if meta.get("type") == "code" and not is_test_path(path):
            if module_summary_path and Path(module_summary_path).exists():
                meta["module_summary_path"] = module_summary_path
            else:
                missing_module_summaries.append((path, meta))
        config_summary_path = prev.get("config_summary_path")
        if meta.get("type") == "config":
            if config_summary_path and Path(config_summary_path).exists():
                meta["config_summary_path"] = config_summary_path
            else:
                missing_config_summaries.append((path, meta))

    return missing_summaries, missing_module_summaries, missing_config_summaries


def cleanup_orphan_summaries(
    file_map: Dict[str, Dict],
    summaries_dir: Path,
    module_summaries_dir: Path,
    config_summaries_dir: Path,
) -> None:
    referenced_summary_paths = set()
    for meta in file_map.values():
        for key in ("summary_path", "module_summary_path", "config_summary_path"):
            path = meta.get(key)
            if path:
                referenced_summary_paths.add(str(Path(path).resolve()))

    for summary_dir in (summaries_dir, module_summaries_dir, config_summaries_dir):
        if not summary_dir.exists():
            continue
        to_remove: List[Path] = []
        for summary_path in summary_dir.glob("*.md"):
            if str(summary_path.resolve()) not in referenced_summary_paths:
                to_remove.append(summary_path)
        total = len(to_remove)
        if total:
            import time
            done = 0
            start = time.time()
            log_every = 5
            for summary_path in to_remove:
                try:
                    summary_path.unlink()
                except FileNotFoundError:
                    pass
                done += 1
                if done % log_every == 0 or done == total:
                    elapsed = int(time.time() - start)
                    print(f"[ai-docs] cleanup summaries progress: {done}/{total} ({elapsed}s)")


def cleanup_deleted_summaries(deleted: Dict[str, Dict]) -> None:
    total = len(deleted)
    if total:
        import time
        done = 0
        start = time.time()
        log_every = 5
    for path, meta in deleted.items():
        summary_path = meta.get("summary_path")
        if summary_path:
            try:
                Path(summary_path).unlink()
            except FileNotFoundError:
                pass
        module_summary_path = meta.get("module_summary_path")
        if module_summary_path:
            try:
                Path(module_summary_path).unlink()
            except FileNotFoundError:
                pass
        config_summary_path = meta.get("config_summary_path")
        if config_summary_path:
            try:
                Path(config_summary_path).unlink()
            except FileNotFoundError:
                pass
        if total:
            done += 1
            if done % log_every == 0 or done == total:
                elapsed = int(time.time() - start)
                print(f"[ai-docs] cleanup deleted summaries progress: {done}/{total} ({elapsed}s)")
