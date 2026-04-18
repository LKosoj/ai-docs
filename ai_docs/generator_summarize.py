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
    sem = asyncio.Semaphore(max(1, threads))
    lock = asyncio.Lock()
    output_dirs = {
        "summary": summaries_dir,
        "module_summary": module_summaries_dir,
        "config_summary": config_summaries_dir,
    }

    async def run_one(path: str, meta: Dict) -> None:
        nonlocal done
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
                save_cb()
                async with lock:
                    done += 1
                    if done % log_every == 0 or done == total:
                        elapsed = int(time.time() - start)
                        print(f"[ai-docs] {label}: {done}/{total} ({elapsed}s)")
            except Exception as exc:
                errors.append(f"{label}: {path} -> {exc}")

    await asyncio.gather(*(run_one(path, meta) for path, meta in items))
