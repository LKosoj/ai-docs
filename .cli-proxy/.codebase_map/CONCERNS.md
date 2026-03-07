# Concerns

## Technical Debt

| Area | Concern | Severity |
|------|---------|----------|
| `ai_docs/llm.py` | No tests for retry/backoff logic, timeout adjustment | Major |
| `ai_docs/generator*.py` | 5 generator modules with no test coverage | Major |
| `ai_docs/domain.py` | classify_type/detect_domains untested despite complex logic | Major |
| `ai_docs/tokenizer.py` | No tests for fallback encoding, chunking edge cases | Minor |

## Code Quality

| File | Issue |
|------|-------|
| `ai_docs/llm.py:72-94` | Complex retry loop with 10+ conditions in single `except` block |
| `ai_docs/scanner.py:168-195` | `_scan_directory` does classification + reading + domain detection (SRP violation) |
| `ai_docs/generator_summarize.py` | 6 similar async functions with duplicated progress logging logic |

## Error Handling

| Location | Pattern | Risk |
|----------|---------|------|
| `llm.py:88` | `raise RuntimeError(f"LLM request failed: {exc}")` | Loses original exception type |
| `scanner.py:142` | `except OSError: continue` | Silent failures on stat errors |
| `cache.py:34` | Catches `JSONDecodeError`, writes `.bad` file | No alerting mechanism |

## Performance

| Concern | File |
|---------|------|
| No streaming for large file summarization | `generator_summarize.py` |
| All file content loaded into memory during scan | `scanner.py:_scan_directory` |
| LLM cache grows unbounded (no eviction) | `llm.py:chat()` |

## Security

| Issue | File |
|-------|------|
| `ssl.verify=False` in HTTP client | `llm.py:28` |
| No input validation on `--source` argument | `cli.py` |
| Temp directory with predictable prefix | `scanner.py:_clone_repo` |

## Maintainability

| Concern | Impact |
|---------|--------|
| No type hints in `generator*.py` modules | Harder refactoring |
| Magic numbers in timeout calculations (`t_min=1000`, `t_max=250000`) | Unclear thresholds |
| Environment variable names not centralized | Configuration drift risk |

## Documentation Gaps

| Module | Missing |
|--------|---------|
| `generator_cache.py` | No docstrings for 8 public functions |
| `generator_sections.py` | No docstrings for build_sections, generate_readme |
| `summary.py` | No docstrings for summarize_file, write_summary |

## Dependencies

| Risk | Detail |
|------|--------|
| `tiktoken` fallback | Silent fallback to `_ByteEncoding` may produce incorrect counts |
| `pathspec` gitignore parsing | No version pinning, potential breaking changes |
| `httpx` with verify=False | Disables SSL verification globally for LLM client |
