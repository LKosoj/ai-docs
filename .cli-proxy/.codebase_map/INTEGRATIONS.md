# Integrations

## LLM Providers
- **OpenAI API** — default provider (`api.openai.com`)
- **Compatible APIs** — any OpenAI-compatible endpoint via `OPENAI_BASE_URL`
- Async client with retry logic (5 retries, exponential backoff)
- Token-based timeout calculation (60s–1200s)
- Response caching by SHA256 hash

## Environment Variables (.env.example)
```
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_CONTEXT_TOKENS=128000
OPENAI_MAX_TOKENS=12000
OPENAI_TEMPERATURE=0.2
AI_DOCS_THREADS=5
AI_DOCS_LOCAL_SITE=false
```

## File System
- **Scanner**: Walks directories with gitignore support (`pathspec`)
- **Cache**: `.ai_docs_cache/` for incremental builds
- **Output**: `.ai-docs/` for generated markdown files
- **Site**: `ai_docs_site/` for built MkDocs static site

## Version Control
- **Git clone**: Supports remote repos via `--source <url>`
- **Gitignore**: Respects `.gitignore` and `.build_ignore`
- **Default excludes**: .git, .venv, node_modules, dist, build, .idea, .vscode

## MkDocs Integration
- Config: `mkdocs.yml` auto-generated
- Plugins: `search`, `mermaid2`
- Extensions: tables, admonition, fenced_code, pymdownx
- Navigation: auto-built from module structure

## CLI Interface
```bash
ai-docs --source <path|url> [--readme] [--mkdocs] [--language ru|en]
ai-docs --source . --regen architecture,configs,changes
```

## Testing
- `tests/test_scanner.py` — Scanner tests
- `tests/test_cache.py` — Cache manager tests
- `tests/test_changes.py` — Change detection tests
