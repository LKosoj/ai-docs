import asyncio
import time
from pathlib import Path
from typing import Dict, List, Tuple

from .generator_shared import is_test_path
from .summary import summarize_file_outputs, write_summary


async def summarize_entries(
    items: List[Tuple[str, Dict]],
    summaries_dir: Path,
    module_summaries_dir: Path,
    config_summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
    label: str,
) -> None:
    if not items:
        return

    total = len(items)
    done = 0
    start = time.time()
    log_every = 5
    save_every = max(10, min(50, total // 10 or 1))
    save_interval = 5.0
    last_save = start
    since_last_save = 0
    sem = asyncio.Semaphore(max(1, threads))
    lock = asyncio.Lock()
    output_dirs = {
        "summary": summaries_dir,
        "module_summary": module_summaries_dir,
        "config_summary": config_summaries_dir,
    }

    async def run_one(path: str, meta: Dict) -> None:
        nonlocal done, last_save, since_last_save
        async with sem:
            try:
                outputs = await summarize_file_outputs(
                    meta["content"],
                    meta["type"],
                    meta["domains"],
                    llm,
                    llm_cache,
                    llm.model,
                    include_module_summary=meta.get("type") == "code" and not is_test_path(path),
                    include_config_summary=meta.get("type") == "config",
                )
                for output_key, content in outputs.items():
                    out_dir = output_dirs[output_key]
                    path_key = f"{output_key}_path" if output_key != "summary" else "summary_path"
                    text_key = f"{output_key}_text" if output_key != "summary" else "summary_text"
                    summary_path = write_summary(out_dir, path, content)
                    meta[path_key] = str(summary_path)
                    meta[text_key] = content
                async with lock:
                    done += 1
                    since_last_save += 1
                    now = time.time()
                    if since_last_save >= save_every or (now - last_save) >= save_interval or done == total:
                        save_cb()
                        since_last_save = 0
                        last_save = now
                    if done % log_every == 0 or done == total:
                        elapsed = int(now - start)
                        print(f"[ai-docs] {label}: {done}/{total} ({elapsed}s)")
            except Exception as exc:
                errors.append(f"{label}: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in items))
