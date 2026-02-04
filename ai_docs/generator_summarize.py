import asyncio
from pathlib import Path
from typing import Dict, List, Tuple
import time

from .summary import summarize_file, write_summary
from .generator_shared import is_test_path


async def summarize_changed_files(
    to_summarize: List[Tuple[str, Dict]],
    summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    if not to_summarize:
        return
    sem = asyncio.Semaphore(max(1, threads))

    async def run_one(path: str, meta: Dict) -> None:
        async with sem:
            try:
                summary = await summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, False)
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in to_summarize))


async def summarize_changed_modules(
    to_summarize: List[Tuple[str, Dict]],
    module_summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    module_candidates = [
        (path, meta)
        for path, meta in to_summarize
        if meta.get("type") == "code" and not is_test_path(path)
    ]
    if not module_candidates:
        return
    sem = asyncio.Semaphore(max(1, threads))

    async def run_one(path: str, meta: Dict) -> None:
        async with sem:
            try:
                summary = await summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize module: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in module_candidates))


async def summarize_changed_configs(
    to_summarize: List[Tuple[str, Dict]],
    config_summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    config_candidates = [
        (path, meta)
        for path, meta in to_summarize
        if meta.get("type") == "config"
    ]
    if not config_candidates:
        return
    sem = asyncio.Semaphore(max(1, threads))

    async def run_one(path: str, meta: Dict) -> None:
        async with sem:
            try:
                summary = await summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize config: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in config_candidates))


async def summarize_missing(
    missing_summaries: List[Tuple[str, Dict]],
    summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    total = len(missing_summaries)
    done = 0
    start = time.time()
    log_every = 5
    if not missing_summaries:
        return
    sem = asyncio.Semaphore(max(1, threads))
    lock = asyncio.Lock()

    async def run_one(path: str, meta: Dict) -> None:
        nonlocal done
        async with sem:
            try:
                summary = await summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, False)
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                save_cb()
                async with lock:
                    done += 1
                    if done % log_every == 0 or done == total:
                        elapsed = int(time.time() - start)
                        print(f"[ai-docs] summarize progress: {done}/{total} ({elapsed}s)")
            except Exception as exc:
                errors.append(f"summarize: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in missing_summaries))


async def summarize_missing_modules(
    missing_module_summaries: List[Tuple[str, Dict]],
    module_summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    total = len(missing_module_summaries)
    done = 0
    start = time.time()
    log_every = 5
    if not missing_module_summaries:
        return
    sem = asyncio.Semaphore(max(1, threads))
    lock = asyncio.Lock()

    async def run_one(path: str, meta: Dict) -> None:
        nonlocal done
        async with sem:
            try:
                summary = await summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                save_cb()
                async with lock:
                    done += 1
                    if done % log_every == 0 or done == total:
                        elapsed = int(time.time() - start)
                        print(f"[ai-docs] summarize modules progress: {done}/{total} ({elapsed}s)")
            except Exception as exc:
                errors.append(f"summarize module: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in missing_module_summaries))


async def summarize_missing_configs(
    missing_config_summaries: List[Tuple[str, Dict]],
    config_summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    total = len(missing_config_summaries)
    done = 0
    start = time.time()
    log_every = 5
    if not missing_config_summaries:
        return
    sem = asyncio.Semaphore(max(1, threads))
    lock = asyncio.Lock()

    async def run_one(path: str, meta: Dict) -> None:
        nonlocal done
        async with sem:
            try:
                summary = await summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                save_cb()
                async with lock:
                    done += 1
                    if done % log_every == 0 or done == total:
                        elapsed = int(time.time() - start)
                        print(f"[ai-docs] summarize configs progress: {done}/{total} ({elapsed}s)")
            except Exception as exc:
                errors.append(f"summarize config: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in missing_config_summaries))
