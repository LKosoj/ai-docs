# Node: ai_docs_site

Generated: 2026-03-07T07:34:06Z

## Purpose
Instruction node for `ai_docs_site` area.

## Scope
- Source glob: `ai_docs_site/**`
- Estimated files: 60

## Instructions for agent
- Read only files relevant to the active task.
- Prefer deterministic checks before edits.
- Keep changes minimal and validate with tests/linters where applicable.

## Source of truth
- `ai_docs_site/**`
- `ai_docs_site/404.html`
- `ai_docs_site/configs/files/pyproject__toml.html`
- `ai_docs_site/css/base.css`
- `ai_docs_site/img/favicon.ico`
- `ai_docs_site/js/base.js`
- `ai_docs_site/modules/ai_docs/__init____py.html`
- `ai_docs_site/search/lunr.js`
- `ai_docs_site/webfonts/fa-brands-400.ttf`
- `ai_docs_site/_index.json`
- `ai_docs_site/css/bootstrap.min.css.map`

## When to update
- Any commit touching `ai_docs_site/**`.
- Any commit touching `ai_docs/**` because this node has import/call dependency on it.
- Any commit touching `mkdocs.yml` because this node has import/call dependency on it.
- Any commit touching `pyproject.toml` because this node has import/call dependency on it.
- Any architecture or behavior change affecting this area.

## Related nodes
- `nodes/ai-docs.md`
- `nodes/mkdocs-yml.md`
- `nodes/pyproject-toml.md`
- `ai_docs` confidence=0.88 via L0
- `mkdocs.yml` confidence=0.86 via L0
- `pyproject.toml` confidence=0.63 via L0

## Owner
- project-maintainers

## Last reviewed
- 2026-03-07T07:34:06Z
