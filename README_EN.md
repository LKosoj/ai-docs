# ai_docs — technical documentation generator

 [Русская версия](README.md) | [English version](README_EN.md)

## Overview
`ai_docs` is a CLI tool for generating technical documentation from code and configuration files.
It supports local folders, local git projects, and remote git repositories.
It generates a `README.md` and a MkDocs site (with automatic build).

Key features:
- Automatic detection of infrastructure domains (Kubernetes, Helm, Terraform, Ansible, Docker, CI/CD, Observability, Service Mesh / Ingress, Data / Storage)
- Incremental generation and caching
- Respects `.gitignore` and filters files
- Parallel LLM summarization (`--threads` / `AI_DOCS_THREADS`)
- Change report in `docs/changes.md`

## Quick start

1) Install dependencies:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Alternative (install as a package):
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install ai-docs-gen
```

Local editable install:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

2) Configure environment variables (example — `.env.example`):
```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192
OPENAI_TEMPERATURE=0.2
AI_DOCS_THREADS=1
AI_DOCS_LOCAL_SITE=false
```

If the tool is installed as a package, you can set environment variables like this:
```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_BASE_URL=""
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_MAX_TOKENS="1200"
export OPENAI_CONTEXT_TOKENS="8192"
export OPENAI_TEMPERATURE="0.2"
export AI_DOCS_THREADS="1"
export AI_DOCS_LOCAL_SITE="false"
```

3) Generate README and MkDocs:
```bash
python -m ai_docs --source .
```

Alternative:
```bash
python ai_docs --source .
```

If installed as a package:
```bash
ai-docs --source .
```

Windows note:
- Paths are handled correctly, but internally normalized to `/`.
- If you use PowerShell, example venv activation and env vars:
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
$env:OPENAI_API_KEY="your_api_key_here"
$env:OPENAI_BASE_URL=""
$env:OPENAI_MODEL="gpt-4o-mini"
$env:OPENAI_MAX_TOKENS="1200"
$env:OPENAI_CONTEXT_TOKENS="8192"
$env:OPENAI_TEMPERATURE="0.2"
$env:AI_DOCS_THREADS="1"
$env:AI_DOCS_LOCAL_SITE="false"
```

## Usage examples

Local folder:
```bash
python -m ai_docs --source /path/to/project
```

Local git project:
```bash
python -m ai_docs --source ~/projects/my-repo
```

Remote repository:
```bash
python -m ai_docs --source https://github.com/org/repo.git
```

README only:
```bash
python -m ai_docs --source . --readme
```

MkDocs only:
```bash
python -m ai_docs --source . --mkdocs
```

Local mode for MkDocs:
```bash
python -m ai_docs --source . --mkdocs --local-site
```

## CI/CD integration
Example for GitHub Actions:
```yaml
- name: Generate Docs
  run: |
    pip install ai-docs-gen
    ai-docs --source . --mkdocs --readme --language en --force
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## What gets generated
- `README.md` — short project description
- `.ai-docs/` — documentation pages
- `.ai-docs/changes.md` — changes since the last generation
- `.ai-docs/modules/` — detailed module docs (one page per module, Doxygen‑like descriptions of functions/classes/params)
- `.ai-docs/configs/` — project config docs (overview + per‑config pages in a unified style)
- `.ai-docs/_index.json` — documentation navigation index (routing rules, list of sections/modules)
- `mkdocs.yml` — MkDocs config
- `ai_docs_site/` — built MkDocs site
- `.ai_docs_cache/` — cache and intermediate summary files

## Supported languages and extensions
Support is based on code extensions in `ai_docs/domain.py`:
`.py`, `.pyi`, `.pyx`, `.js`, `.jsx`, `.ts`, `.tsx`, `.go`, `.java`, `.c`, `.cc`, `.cpp`, `.h`, `.hpp`, `.rs`, `.rb`, `.php`, `.cs`, `.kt`, `.kts`, `.swift`, `.m`, `.mm`, `.vb`, `.bas`, `.sql`, `.pas`, `.dpr`, `.pp`, `.r`, `.pl`, `.pm`, `.f`, `.for`, `.f90`, `.f95`, `.f03`, `.f08`, `.sb3`, `.adb`, `.ads`, `.asm`, `.s`, `.ino`, `.htm`, `.html`, `.css`.

## Documentation index
The `.ai-docs/_index.json` file is built automatically and contains:
- list of sections and modules (paths and short descriptions);
- routing rules: priority `modules/index.md → modules/* → index.md/architecture.md/conventions.md`;
- ranking principle: keyword match frequency + file priority.

## .ai-docs.yaml (extensions)
If the project contains `.ai-docs.yaml`, it defines a priority list of extensions to scan.
If the file is missing, it is generated automatically from current `*_EXTENSIONS`.

Format (map and list are supported for extensions):
```yaml
code_extensions:
  .py: Python
  .ts: TypeScript
doc_extensions:
  .md: Markdown
  .rst: reStructuredText
config_extensions:
  .yml: YAML
  .json: JSON
exclude:
  - "temp/*"
  - "*.log"
```

## CLI parameters
- `--source <path|url>` — source
- `--output <path>` — output directory (default: source for local paths, `./output/<repo>` for URL)

## Testing
Tests are in `tests/`:
- `test_cache.py`
- `test_changes.py`
- `test_scanner.py`

Run (from repo root):
```bash
python -m pytest
```
- `--readme` — generate only README
- `--mkdocs` — generate only MkDocs
- `--language ru|en` — documentation language
- `--include/--exclude` — filters
- `--max-size` — max file size
- `--threads` — number of LLM threads
- `--cache-dir` — cache directory (default `.ai_docs_cache`)
- `--no-cache` — disable LLM cache
- `--local-site` — add `site_url` and `use_directory_urls` to `mkdocs.yml`
- `--force` — overwrite `README.md` if it already exists
- `--regen` — comma-separated list of sections to force regeneration (e.g. `architecture,configs,changes`, or `all`)

Default behavior: if neither `--readme` nor `--mkdocs` is specified, both are generated.
Docs sections in `.ai-docs/*.md` are not regenerated if the file already exists, unless listed in `--regen`.
If the module count is below `AI_DOCS_REGEN_ALL_THRESHOLD` (default 50), all sections are regenerated automatically.
When running without parameters for sections, a hint is printed with a `--regen` example.
If there are more than 100 modules, `modules/index.md` is paginated into pages of 100 items with ←/→ navigation.
If there are more than 100 configs, `configs/index.md` is paginated into pages of 100 items with ←/→ navigation.

## MkDocs
Build runs automatically at the end of generation:
```
mkdocs build -f mkdocs.yml
```

## Exclusions
The scanner respects `.gitignore`, `.build_ignore`, and default exclusions:
`.venv`, `node_modules`, `ai_docs_site`, `.ai-docs`, `.ai_docs_cache`, `dist`, `build`, etc.

## Development and contribution
- Install dependencies (see “Quick start”)
- Run via `python -m ai_docs ...` for debugging
- PRs and suggestions are welcome

## License
MIT
