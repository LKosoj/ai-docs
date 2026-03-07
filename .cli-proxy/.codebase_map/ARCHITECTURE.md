# Architecture

## Overview

**ai-docs** — CLI-инструмент для генерации технической документации (README + MkDocs) по коду и конфигурациям репозитория с использованием LLM.

## Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  ai_docs/cli.py (argparse) → ai_docs/__main__.py            │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│     Scanner Layer       │      │      LLM Layer          │
│  ai_docs/scanner.py     │      │   ai_docs/llm.py        │
│  - scan_source()        │      │   - LLMClient           │
│  - _scan_directory()    │      │   - from_env()          │
│  - classify_type()      │      │   - chat() w/cache      │
│  - detect_domains()     │      │   - retry/backoff       │
└─────────────────────────┘      └─────────────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Generator Layer                           │
│  ai_docs/generator.py (orchestrator)                        │
│  ├── ai_docs/generator_cache.py  (diff, carry, cleanup)     │
│  ├── ai_docs/generator_sections.py (build sections)         │
│  ├── ai_docs/generator_summarize.py (LLM summarization)     │
│  └── ai_docs/generator_output.py (write docs)               │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│      Domain Layer       │      │      Cache Layer        │
│  ai_docs/domain.py      │      │  ai_docs/cache.py       │
│  - extension maps       │      │  - CacheManager         │
│  - infra detection      │      │  - diff_files()         │
└─────────────────────────┘      └─────────────────────────┘
```

## Data Flow

1. **Scan**: `cli.main()` → `scan_source()` → `_scan_directory()`
   - Applies include/exclude patterns (`.ai-docs.yaml`, `.gitignore`)
   - Classifies files: `code`, `config`, `docs`, `infra`, `ci`, `data`
   - Detects domains: `kubernetes`, `docker`, `terraform`, `helm`, etc.

2. **Diff**: `generator.py` → `diff_files()` via `CacheManager`
   - Compares current scan with cached index
   - Categories: `added`, `modified`, `deleted`, `unchanged`

3. **Summarize**: Parallel LLM calls (`threads=N`)
   - `summarize_changed_files()` → per-file summaries
   - `summarize_changed_modules()` → module-level summaries
   - `summarize_changed_configs()` → config summaries
   - `summarize_missing*()` → carry forward unchanged

4. **Build Sections**: `build_sections()` → `ai_docs/.ai-docs/`
   - `architecture.md`, `runtime.md`, `changes.md`, `index.md`
   - `modules/*.md`, `configs/*.md`

5. **Output**:
   - `README.md` (root)
   - `mkdocs.yml` (with nav structure)
   - `ai_docs_site/` (static HTML via `mkdocs build`)

## Key Patterns

| Pattern | Location |
|---------|----------|
| Async orchestration | `generator._generate_docs_async()` |
| LLM caching (SHA256) | `llm.LLMClient.chat(cache=...)` |
| Incremental gen | Only changed files summarized |
| Domain detection | `domain.detect_domains()` by path + content |
| Config-driven | `.ai-docs.yaml` for extensions/excludes |

## Dependencies

- **LLM**: OpenAI-compatible API (`OPENAI_API_KEY`, `OPENAI_BASE_URL`)
- **Token counting**: `tiktoken`
- **Config parsing**: `pyyaml`, `tomli`
- **Path matching**: `pathspec` (gitignore patterns)
