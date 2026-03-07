# Project Structure

```
/srv/git_projects/ai-docs/
├── ai_docs/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (imports cli.main)
│   ├── cli.py               # CLI argparse, main()
│   ├── scanner.py           # Repo scanning, classification
│   ├── domain.py            # Extension maps, domain detection
│   ├── utils.py             # SHA256, file utils, is_binary
│   ├── llm.py               # LLMClient (OpenAI API wrapper)
│   ├── tokenizer.py         # Token counting (tiktoken)
│   ├── cache.py             # CacheManager (index.json, llm_cache.json)
│   ├── changes.py           # format_changes_md()
│   ├── generator.py         # Main orchestrator (async)
│   ├── generator_cache.py   # Diff, carry, cleanup helpers
│   ├── generator_sections.py# Build section files
│   ├── generator_summarize.py# LLM summarization routines
│   ├── generator_output.py  # Write README, MkDocs
│   ├── generator_shared.py  # DOMAIN_TITLES, SECTION_TITLES
│   ├── mkdocs.py            # MkDocs config generation
│   ├── summary.py           # Summary helpers
│   └── assets/
│       └── mermaid.min.js   # Diagram rendering
│
├── tests/
│   ├── __init__.py
│   ├── test_cache.py
│   ├── test_changes.py
│   └── test_scanner.py
│
├── .ai-docs.yaml            # Project config (extensions, excludes)
├── pyproject.toml           # Package metadata, dependencies
├── mkdocs.yml               # MkDocs source config
├── documentary.skill        # Skill definition
├── run_docs_bg.sh           # Background runner script
│
├── .ai-docs/                # Generated docs (output)
├── .ai_docs_cache/          # LLM cache, index snapshots
├── ai_docs_site/            # Built MkDocs site (HTML)
│   ├── index.html
│   ├── architecture.html
│   ├── runtime.html
│   ├── conventions.html
│   ├── glossary.html
│   └── sitemap.xml
│
└── logs/                    # Runtime logs
```

## Core Modules

| File | Responsibility | Key Functions |
|------|----------------|---------------|
| `cli.py` | CLI interface | `parse_args()`, `main()` |
| `scanner.py` | Repo scanning | `scan_source()`, `_scan_directory()`, `classify_type()`, `detect_domains()` |
| `domain.py` | Domain logic | Extension maps, infra detection |
| `llm.py` | LLM client | `LLMClient.chat()`, `from_env()` |
| `generator.py` | Orchestration | `generate_docs()`, `_generate_docs_async()` |
| `generator_cache.py` | Incremental gen | `diff_files()`, `carry_unchanged_summaries()` |
| `generator_summarize.py` | Summarization | `summarize_changed_*()` |
| `cache.py` | Persistence | `CacheManager.load/save_*()` |

## Generated Artifacts

| Path | Description |
|------|-------------|
| `.ai-docs/architecture.md` | System architecture |
| `.ai-docs/runtime.md` | Runtime behavior |
| `.ai-docs/changes.md` | Delta since last gen |
| `.ai-docs/index.md` | Module index |
| `.ai-docs/modules/*.md` | Per-module summaries |
| `.ai-docs/configs/*.md` | Per-config summaries |
| `README.md` | Project overview |
| `mkdocs.yml` | Site navigation |

## Config Files

| File | Purpose |
|------|---------|
| `.ai-docs.yaml` | Extensions, exclude patterns |
| `pyproject.toml` | Package deps, entry points |
| `.gitignore` | Scan exclusions |
| `.build_ignore` | Additional exclusions |
