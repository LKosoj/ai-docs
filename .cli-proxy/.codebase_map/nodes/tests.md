# Node: tests

## Purpose
Unit tests for `ai_docs` package — validates cache diff logic, scanner filtering, and changes markdown formatting.

## Scope
- **Source glob**: `tests/**` (3 test files)
- **Framework**: `unittest` (stdlib), no pytest dependency
- **Coverage**: ~20% (cache, scanner, changes only)
- **Test files**: `test_cache.py`, `test_scanner.py`, `test_changes.py`

## Instructions for agent
- **Run all**: `python -m unittest discover -s tests` or `pytest -q tests/`
- **Run single**: `python -m unittest tests.test_cache.CacheManagerTests.test_diff_files`
- **Test pattern**: `unittest.TestCase` classes, `test_*` methods, `tempfile.TemporaryDirectory()` for isolation
- **Add tests**: Required for any new/changed behavior in `ai_docs/`
- **Gaps**: No tests for `llm.py`, `generator*.py`, `summary.py`, `domain.py` — prioritize these

## Source of truth
- **Test root**: `tests/`
- **Cache tests**: `tests/test_cache.py` (CacheManager.diff_files, save/load index)
- **Scanner tests**: `tests/test_scanner.py` (scan_source, .gitignore, .venv exclusion)
- **Changes tests**: `tests/test_changes.py` (format_changes_md output validation)
- **Test utils**: `tests/__init__.py` (empty package marker)

## When to update
- **Direct**: Any change to `tests/*.py` (new tests, fixes, refactors).
- **Source changes**: Any modification to `ai_docs/cache.py`, `ai_docs/scanner.py`, `ai_docs/changes.py` requires test updates.
- **New features**: Add tests for new modules (priority: `llm.py`, `generator.py`, `summary.py`, `domain.py`).
- **Bug fixes**: Add regression test before fixing.
- **Framework changes**: Switch to pytest requires updating all test files.

## Related nodes
- `ai-docs.md` — tested package (direct dependency)
- `ai-docs-cache.md` — cache logic tested in `test_cache.py`
- `ai-docs-scanner.md` — scanner logic tested in `test_scanner.py`

## Owner
- `project-maintainers`

## Last reviewed
- 2026-03-17
