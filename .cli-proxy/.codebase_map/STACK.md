# Technology Stack

## Runtime

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | ≥3.8 | Runtime environment |
| **Package manager** | pip + requirements.txt | Dependency management |
| **Build system** | setuptools ≥68 | Package building |

## Core Dependencies

### LLM & AI
| Package | Purpose |
|---------|---------|
| `openai` | OpenAI API client (LLM calls) |
| `tiktoken` | Token counting (GPT models) |
| `httpx` | Async HTTP client (LLM transport) |

### Data Processing
| Package | Purpose |
|---------|---------|
| `pyyaml` | YAML config parsing |
| `tomli` | TOML parsing (pyproject.toml) |
| `pathspec` | Gitignore pattern matching |
| `requests` | HTTP requests (fallback) |

### Documentation
| Package | Purpose |
|---------|---------|
| `mkdocs` | Static site generation |
| `mkdocs-mermaid2-plugin` | Mermaid diagram rendering |
| `pymdown-extensions` | Markdown extensions |

### Utilities
| Package | Purpose |
|---------|---------|
| `python-dotenv` | Environment variables (.env) |

## External Services

### LLM Providers
- **OpenAI-compatible APIs** — через `AsyncOpenAI` клиент
- Поддержка кастомных endpoint (`OPENAI_BASE_URL`)
- Модели: GPT-4o-mini (default), любые совместимые

## File Formats

### Input
| Format | Extensions | Parser |
|--------|------------|--------|
| Python | `.py`, `.pyi`, `.pyx` | text |
| JavaScript/TypeScript | `.js`, `.jsx`, `.ts`, `.tsx` | text |
| YAML | `.yml`, `.yaml` | `pyyaml` |
| TOML | `.toml` | `tomli` |
| JSON | `.json` | `json` (stdlib) |
| Markdown | `.md` | text |
| Dockerfile | `Dockerfile*` | text |
| Terraform | `.tf`, `.tfvars` | text |

### Output
| Format | Purpose |
|--------|---------|
| Markdown (`.md`) | Documentation source |
| YAML (`.yml`) | MkDocs config |
| HTML | Static site (`ai_docs_site/`) |
| JSON | Cache snapshots (`index.json`, `llm_cache.json`) |

## Infrastructure

### Build & Distribution
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project.scripts]
ai-docs = "ai_docs.cli:main"
```

### Package Data
- `ai_docs/assets/mermaid.min.js` — Mermaid библиотека (1.6MB, minified)

## Browser Dependencies (Generated Site)

| Library | Purpose |
|---------|---------|
| **Bootstrap CSS** | Styling |
| **Font Awesome** | Icons |
| **Mermaid.js** | Diagram rendering |
| **Lunr.js** | Client-side search |

## Token Counting

**Engine**: `tiktoken`
- Encodings: `cl100k_base` (fallback)
- Model-specific: через `tiktoken.encoding_for_model()`
- Chunking: по границам токенов (max 1800 tokens/chunk)

## Async Runtime

- **Event loop**: `asyncio` (stdlib)
- **Concurrency**: `asyncio.Semaphore`, `asyncio.gather()`
- **HTTP**: `httpx.AsyncClient` (verify=False для self-signed)

## System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Python | 3.8 | 3.10+ |
| RAM | 512 MB | 1 GB+ |
| Disk | 100 MB | 500 MB+ (кэш) |
| Network | — | Доступ к LLM API |
