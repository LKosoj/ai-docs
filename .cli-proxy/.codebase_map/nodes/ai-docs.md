# Node: ai_docs

Generated: 2026-03-07T07:34:06Z

## Purpose
Instruction node for `ai_docs` area.

## Scope
- Source glob: `ai_docs/**`
- Estimated files: 19

## Instructions for agent
- Read only files relevant to the active task.
- Prefer deterministic checks before edits.
- Keep changes minimal and validate with tests/linters where applicable.

## Source of truth
- `ai_docs/**`
- `ai_docs/__init__.py`
- `ai_docs/assets/mermaid.min.js`
- `ai_docs/__main__.py`
- `ai_docs/cache.py`
- `ai_docs/changes.py`
- `ai_docs/cli.py`
- `ai_docs/domain.py`
- `ai_docs/generator.py`
- `ai_docs/generator_cache.py`
- `ai_docs/generator_output.py`

## Module API
Детальные интерфейсы модулей этой области:

- [ai_docs/cache.py](../api/ai_docs/cache-py.md)
- [ai_docs/changes.py](../api/ai_docs/changes-py.md)
- [ai_docs/cli.py](../api/ai_docs/cli-py.md)
- [ai_docs/domain.py](../api/ai_docs/domain-py.md)
- [ai_docs/generator.py](../api/ai_docs/generator-py.md)
- [ai_docs/generator_cache.py](../api/ai_docs/generator_cache-py.md)
- [ai_docs/generator_output.py](../api/ai_docs/generator_output-py.md)
- [ai_docs/generator_sections.py](../api/ai_docs/generator_sections-py.md)
- [ai_docs/generator_shared.py](../api/ai_docs/generator_shared-py.md)
- [ai_docs/generator_summarize.py](../api/ai_docs/generator_summarize-py.md)

## When to update
- Any commit touching `ai_docs/**`.
- Any commit touching `ai_docs_site/**` because this node has import/call dependency on it.
- Any commit touching `mkdocs.yml` because this node has import/call dependency on it.
- Any commit touching `pyproject.toml` because this node has import/call dependency on it.
- Any commit touching `run_docs_bg.sh` because this node has import/call dependency on it.
- Any architecture or behavior change affecting this area.

## Related nodes
- `nodes/ai-docs-site.md`
- `nodes/mkdocs-yml.md`
- `nodes/pyproject-toml.md`
- `nodes/run-docs-bg-sh.md`
- `ai_docs_site` confidence=0.88 via L0
- `mkdocs.yml` confidence=0.90 via L0
- `pyproject.toml` confidence=0.88 via L0
- `run_docs_bg.sh` confidence=0.63 via L0

## Owner
- project-maintainers

## Last reviewed
- 2026-03-07T07:34:06Z
