# API Spec: `ai_docs/generator_sections.py`

Generated: 2026-03-17T07:32:37Z

## Symbols
- `async def generate_section(llm, llm_cache, title, context, language)` (line 21)
- `async def generate_readme(llm, llm_cache, project_name, overview_context, language)` (line 44)
- `def truncate_context(context, model, max_tokens)` (line 57)
- `async def summarize_chunk(llm, llm_cache, chunk, language, focus)` (line 64)
- `async def build_hierarchical_context(llm, llm_cache, texts, max_tokens, language, label, focus)` (line 86)
- `async def build_sections(file_map, added, modified, deleted, docs_dir, llm, llm_cache, language, threads, input_budget, force_sections)` (line 128)
