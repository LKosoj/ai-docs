# Node: pyproject-toml

## Purpose
Python package configuration for `ai-docs-gen` — defines build system, dependencies, CLI entry point, and package data for documentation generator tool.

## Scope
- **File**: `pyproject.toml` (PEP 517/518 build config)
- **Package name**: `ai-docs-gen` (v0.1.10)
- **CLI command**: `ai-docs` → `ai_docs.cli:main`
- **Python version**: ≥3.8

## Instructions for agent
- **Dependencies**: Any new dependency requires adding to `[project.dependencies]` and updating `requirements.txt` (if used).
- **Entry points**: CLI commands defined in `[project.scripts]` — format: `command = "module:function"`.
- **Package data**: `ai_docs/assets/mermaid.min.js` included via `[tool.setuptools.package-data]`.
- **Build**: `pip install -e .` for development, `pip build` for distribution.
- **Version**: Update `version` in `[project]` following semver (current: 0.1.10).

## Source of truth
- **Config file**: `pyproject.toml` (root directory)
- **Build system**: `setuptools>=68` + `wheel` (PEP 517)
- **Dependencies**:
  - LLM: `openai`, `tiktoken`, `httpx` (via openai)
  - Parsing: `pyyaml`, `tomli`, `pathspec`
  - Docs: `mkdocs`, `mkdocs-mermaid2-plugin`, `pymdown-extensions`
  - Utils: `requests`, `python-dotenv`
- **Entry point**: `ai_docs/cli.py:main()` (argparse CLI)
- **Package structure**: `ai_docs/` (excludes `ai_docs/assets/` from discovery, includes as package-data)

## When to update
- **New dependencies**: Add to `[project.dependencies]` when new libraries are required (e.g., new LLM provider, parser).
- **Version bump**: Update `version` on releases (semver: major.minor.patch).
- **Entry points**: Add/remove CLI commands in `[project.scripts]`.
- **Package structure**: Changes to `ai_docs/` layout require updating `[tool.setuptools.packages.find]`.
- **Build system**: Switching from setuptools to alternative (hatch, poetry) requires full rewrite.
- **Python version**: Update `requires-python` when dropping/adding version support.

## Related nodes
- `ai-docs.md` — main package (entry point `ai_docs.cli:main`)
- `ai-docs-site.md` — MkDocs dependency (mkdocs, mkdocs-mermaid2-plugin)
- `run-docs-bg-sh.md` — shell script that invokes `ai-docs` CLI

## Owner
- `project-maintainers`

## Last reviewed
- 2026-03-17
