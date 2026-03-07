# Node: run_docs_bg.sh

Generated: 2026-03-07T07:34:06Z

## Purpose
Instruction node for `run_docs_bg.sh` area.

## Scope
- Source glob: `run_docs_bg.sh`
- Estimated files: 1

## Instructions for agent
- Read only files relevant to the active task.
- Prefer deterministic checks before edits.
- Keep changes minimal and validate with tests/linters where applicable.

## Source of truth
- `run_docs_bg.sh`
- `run_docs_bg.sh`

## When to update
- Any commit touching `run_docs_bg.sh`.
- Any commit touching `ai_docs/**` because this node has import/call dependency on it.
- Any commit touching `pyproject.toml` because this node has import/call dependency on it.
- Any architecture or behavior change affecting this area.

## Related nodes
- `nodes/ai-docs.md`
- `nodes/pyproject-toml.md`
- `ai_docs` confidence=0.63 via L0
- `pyproject.toml` confidence=0.63 via L0

## Owner
- project-maintainers

## Last reviewed
- 2026-03-07T07:34:06Z
