from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

from .summary import summarize_file, write_summary
from .generator_shared import is_test_path


def summarize_changed_files(
    to_summarize: List[Tuple[str, Dict]],
    summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    if threads > 1 and to_summarize:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            for path, meta in to_summarize:
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        False,
                    )
                ] = (path, meta)
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    errors.append(f"summarize: {path} -> {exc}")
                    continue
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                save_cb()
    else:
        for path, meta in to_summarize:
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, False)
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize: {path} -> {exc}")


def summarize_changed_modules(
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
    if threads > 1 and module_candidates:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            for path, meta in module_candidates:
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        True,
                    )
                ] = (path, meta)
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    errors.append(f"summarize module: {path} -> {exc}")
                    continue
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                save_cb()
    else:
        for path, meta in module_candidates:
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize module: {path} -> {exc}")


def summarize_changed_configs(
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
    if threads > 1 and config_candidates:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            for path, meta in config_candidates:
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        True,
                    )
                ] = (path, meta)
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    errors.append(f"summarize config: {path} -> {exc}")
                    continue
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                save_cb()
    else:
        for path, meta in config_candidates:
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize config: {path} -> {exc}")


def summarize_missing(
    missing_summaries: List[Tuple[str, Dict]],
    summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    if threads > 1 and missing_summaries:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            for path, meta in missing_summaries:
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                    )
                ] = (path, meta)
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    errors.append(f"summarize: {path} -> {exc}")
                    continue
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                save_cb()
    else:
        for path, meta in missing_summaries:
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, False)
                summary_path = write_summary(summaries_dir, path, summary)
                meta["summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize: {path} -> {exc}")


def summarize_missing_modules(
    missing_module_summaries: List[Tuple[str, Dict]],
    module_summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    if threads > 1 and missing_module_summaries:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            for path, meta in missing_module_summaries:
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        True,
                    )
                ] = (path, meta)
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    errors.append(f"summarize module: {path} -> {exc}")
                    continue
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                save_cb()
    else:
        for path, meta in missing_module_summaries:
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(module_summaries_dir, path, summary)
                meta["module_summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize module: {path} -> {exc}")


def summarize_missing_configs(
    missing_config_summaries: List[Tuple[str, Dict]],
    config_summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str],
) -> None:
    if threads > 1 and missing_config_summaries:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            for path, meta in missing_config_summaries:
                futures[
                    executor.submit(
                        summarize_file,
                        meta["content"],
                        meta["type"],
                        meta["domains"],
                        llm,
                        llm_cache,
                        llm.model,
                        True,
                    )
                ] = (path, meta)
            for future in as_completed(futures):
                path, meta = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    errors.append(f"summarize config: {path} -> {exc}")
                    continue
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                save_cb()
    else:
        for path, meta in missing_config_summaries:
            try:
                summary = summarize_file(meta["content"], meta["type"], meta["domains"], llm, llm_cache, llm.model, True)
                summary_path = write_summary(config_summaries_dir, path, summary)
                meta["config_summary_path"] = str(summary_path)
                save_cb()
            except Exception as exc:
                errors.append(f"summarize config: {path} -> {exc}")
