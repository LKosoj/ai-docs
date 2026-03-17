# API Spec: `ai_docs/generator_summarize.py`

Generated: 2026-03-17T07:32:37Z

## Symbols
- `async def summarize_changed_files(to_summarize, summaries_dir, llm, llm_cache, threads, save_cb, errors)` (line 10)
- `async def summarize_changed_modules(to_summarize, module_summaries_dir, llm, llm_cache, threads, save_cb, errors)` (line 47)
- `async def summarize_changed_configs(to_summarize, config_summaries_dir, llm, llm_cache, threads, save_cb, errors)` (line 89)
- `async def summarize_missing(missing_summaries, summaries_dir, llm, llm_cache, threads, save_cb, errors)` (line 131)
- `async def summarize_missing_modules(missing_module_summaries, module_summaries_dir, llm, llm_cache, threads, save_cb, errors)` (line 168)
- `async def summarize_missing_configs(missing_config_summaries, config_summaries_dir, llm, llm_cache, threads, save_cb, errors)` (line 205)
