# Node: mkdocs.yml

Generated: 2026-03-07T07:34:06Z

## Purpose
Instruction node for `mkdocs.yml` area.

## Scope
- Source glob: `mkdocs.yml`
- Estimated files: 1

## Instructions for agent
- Read only files relevant to the active task.
- Prefer deterministic checks before edits.
- Keep changes minimal and validate with tests/linters where applicable.

## Source of truth
- `mkdocs.yml`
- `mkdocs.yml`

## When to update
- Any commit touching `mkdocs.yml`.
- Any commit touching `ai_docs/**` because this node has import/call dependency on it.
- Any commit touching `ai_docs_site/**` because this node has import/call dependency on it.
- Any architecture or behavior change affecting this area.

## Related nodes
- `nodes/ai-docs.md`
- `nodes/ai-docs-site.md`
- `ai_docs` confidence=0.90 via L0
- `ai_docs_site` confidence=0.86 via L0

## Owner
- project-maintainers

## Last reviewed
- 2026-03-07T07:34:06Z
