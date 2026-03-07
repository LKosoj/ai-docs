# Node: tests

Generated: 2026-03-07T07:34:06Z

## Purpose
Instruction node for `tests` area.

## Scope
- Source glob: `tests/**`
- Estimated files: 4

## Instructions for agent
- Read only files relevant to the active task.
- Prefer deterministic checks before edits.
- Keep changes minimal and validate with tests/linters where applicable.

## Source of truth
- `tests/**`
- `tests/__init__.py`
- `tests/test_cache.py`
- `tests/test_changes.py`
- `tests/test_scanner.py`

## Module API
Детальные интерфейсы модулей этой области:

- [tests/test_cache.py](../api/tests/test_cache-py.md)
- [tests/test_changes.py](../api/tests/test_changes-py.md)
- [tests/test_scanner.py](../api/tests/test_scanner-py.md)

## When to update
- Any commit touching `tests/**`.
- Any commit touching `ai_docs/**` because this node has import/call dependency on it.
- Any architecture or behavior change affecting this area.

## Related nodes
- `nodes/ai-docs.md`
- `ai_docs` confidence=0.90 via L1/L2

## Owner
- project-maintainers

## Last reviewed
- 2026-03-07T07:34:06Z
