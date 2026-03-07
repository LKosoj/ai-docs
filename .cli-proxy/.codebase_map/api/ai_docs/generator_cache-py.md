# API Spec: `ai_docs/generator_cache.py`

Generated: 2026-03-07T07:34:06Z

## Symbols
- `def init_cache(cache_dir, use_cache)` (line 9)
- `def build_file_map(files)` (line 17)
- `def diff_files(cache, file_map)` (line 30)
- `def ensure_summary_dirs(cache_dir)` (line 34)
- `def save_cache_snapshot(cache, file_map, index_data, llm_cache, use_cache)` (line 44)
- `def carry_unchanged_summaries(unchanged, prev_files)` (line 60)
- `def cleanup_orphan_summaries(file_map, summaries_dir, module_summaries_dir, config_summaries_dir)` (line 90)
- `def cleanup_deleted_summaries(deleted)` (line 127)
