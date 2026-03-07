# Tech Stack

## Core Language
- **Python 3.8+** — основной язык реализации

## Dependencies (pyproject.toml)
| Package | Purpose |
|---------|---------|
| `openai` | LLM client (OpenAI API compatible) |
| `httpx` | Async HTTP client (LLM requests) |
| `requests` | HTTP utilities |
| `tiktoken` | Token counting for LLM models |
| `pyyaml` | YAML config parsing |
| `pathspec` | Gitignore-style pattern matching |
| `tomli` | TOML parsing |
| `python-dotenv` | Environment variable loading |
| `mkdocs` | Documentation site generation |
| `mkdocs-mermaid2-plugin` | Mermaid diagram support |
| `pymdown-extensions` | Markdown extensions |

## Key Modules
- `ai_docs/cli.py` — CLI entry point (argparse)
- `ai_docs/scanner.py` — Code scanning with gitignore support
- `ai_docs/llm.py` — Async LLM client with retry logic
- `ai_docs/generator.py` — Main documentation generation orchestrator
- `ai_docs/generator_sections.py` — Section generation (architecture, runtime, etc.)
- `ai_docs/generator_summarize.py` — File/module summarization
- `ai_docs/generator_cache.py` — Incremental build cache management
- `ai_docs/domain.py` — File classification and domain detection
- `ai_docs/cache.py` — JSON-based cache manager
- `ai_docs/tokenizer.py` — Token counting utilities
- `ai_docs/utils.py` — Common utilities

## Infrastructure Detection (domain.py)
- **Docker**: Dockerfile, docker-compose.yml
- **Kubernetes**: deployment.yaml, service.yaml, kustomization.yaml
- **Helm**: Chart.yaml, values.yaml
- **Terraform**: *.tf, *.tfvars
- **CI/CD**: .gitlab-ci.yml, Jenkinsfile, .github/workflows/*
- **Observability**: prometheus.yml, grafana, loki, tempo, otel
- **Service Mesh**: istio, linkerd, envoy, ingress

## Output
- **MkDocs** site with Russian/English language support
- **README.md** auto-generation
- **Mermaid** diagrams for architecture
