# Node: ai_docs

## Purpose
Core Python package implementing CLI documentation generator — scans repositories, summarizes files/configs via LLM, generates Markdown + MkDocs site.

## Scope
- **Source glob**: `ai_docs/**` (19 files)
- **Entry points**: `ai_docs/cli.py:main()`, `ai_docs/__main__.py`
- **CLI command**: `ai-docs` (via `pyproject.toml` scripts)
- **Key components**: scanner, LLM client, generator orchestrator, summarizers, MkDocs builder

## Instructions for agent
- **Read first**: `cli.py` (args), `scanner.py` (file discovery), `generator.py` (orchestration).
- **LLM changes**: Always check `llm.py` retry/cache logic and `summary.py` prompts.
- **Test requirement**: Any behavior change needs tests in `tests/` (currently 3 files, ~20% coverage).
- **Run tests**: `pytest -q tests/` or `python -m unittest discover -s tests`.
- **Lint**: `ruff check ai_docs/` before commit.

## Source of truth
- **Package root**: `ai_docs/`
- **CLI**: `ai_docs/cli.py` (argparse, main entry)
- **Scanner**: `ai_docs/scanner.py` (scan_source, _scan_directory, classify_type, detect_domains)
- **LLM**: `ai_docs/llm.py` (LLMClient, from_env, retry/cache)
- **Generator**: `ai_docs/generator.py` (_generate_docs_async, generate_docs)
- **Summarization**: `ai_docs/summary.py` (SUMMARY_PROMPT, MODULE_SUMMARY_PROMPT, summarize_file)
- **Cache**: `ai_docs/cache.py` (CacheManager), `ai_docs/generator_cache.py` (diff, carry, cleanup)
- **Output**: `ai_docs/generator_output.py` (build_mkdocs, write_docs, _postprocess_mermaid_html)
- **Config**: `ai_docs/domain.py` (extension maps, domain detection)
- **Assets**: `ai_docs/assets/mermaid.min.js`

## When to update
- **Direct**: Any change to `ai_docs/*.py` or `ai_docs/assets/**`.
- **Dependency changes**: `pyproject.toml` dependencies (openai, tiktoken, mkdocs, etc.).
- **Config changes**: `.ai-docs.yaml` schema updates (extensions, exclude patterns).
- **Test changes**: `tests/test_*.py` additions or modifications.
- **Output changes**: `ai_docs_site/**` regeneration logic (`generator_output.py`).
- **Script changes**: `run_docs_bg.sh` (background execution).

## Related nodes
- `ai-docs-site.md` — generated HTML output
- `mkdocs-yml.md` — MkDocs configuration
- `pyproject-toml.md` — package dependencies, entry points
- `run-docs-bg-sh.md` — background runner script
- `ai-docs-cache.md` — cache directory structure

## Owner
- `project-maintainers`

## Last reviewed
- 2026-03-17
