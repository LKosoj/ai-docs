# Node: pyproject.toml

Generated: 2026-03-07T07:34:06Z

## Purpose
Instruction node for `pyproject.toml` area.

## Scope
- Source glob: `pyproject.toml`
- Estimated files: 1

## Instructions for agent
- Read only files relevant to the active task.
- Prefer deterministic checks before edits.
- Keep changes minimal and validate with tests/linters where applicable.

## Source of truth
- `pyproject.toml`
- `pyproject.toml`

## When to update
- Any commit touching `pyproject.toml`.
- Any commit touching `ai_docs/**` because this node has import/call dependency on it.
- Any commit touching `ai_docs_site/**` because this node has import/call dependency on it.
- Any commit touching `run_docs_bg.sh` because this node has import/call dependency on it.
- Any architecture or behavior change affecting this area.

## Related nodes
- `nodes/ai-docs.md`
- `nodes/ai-docs-site.md`
- `nodes/run-docs-bg-sh.md`
- `ai_docs` confidence=0.88 via L0
- `ai_docs_site` confidence=0.63 via L0
- `run_docs_bg.sh` confidence=0.63 via L0

## Owner
- project-maintainers

## Last reviewed
- 2026-03-07T07:34:06Z
