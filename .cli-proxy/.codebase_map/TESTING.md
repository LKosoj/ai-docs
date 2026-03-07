# Testing

## Test Suite Overview

| File | Coverage | Lines |
|------|----------|-------|
| `tests/test_cache.py` | `CacheManager.diff_files()` | ~40 |
| `tests/test_scanner.py` | `scan_source()` local scan | ~20 |
| `tests/test_changes.py` | `format_changes_md()` | ~15 |

**Total**: 3 test files, ~75 строк тестов

## Test Files

### `tests/test_cache.py`

**Класс**: `CacheManagerTests`

**Тесты**:
- `test_diff_files` — проверка логики diff:
  -初次 scan → все файлы в `added`
  - Изменение hash → файл в `modified`
  - Новый файл → в `added`
  - Удаление файла → в `deleted`
  - Без изменений → в `unchanged`

**Паттерн**:
```python
with tempfile.TemporaryDirectory() as tmp:
    cache = CacheManager(Path(tmp))
    current = {"a.txt": {"hash": "1"}, "b.txt": {"hash": "2"}}
    added, modified, deleted, unchanged = cache.diff_files(current)
```

### `tests/test_scanner.py`

**Класс**: `ScannerTests`

**Тесты**:
- `test_scan_local_dir` — проверка сканирования:
  - Включает: `app.py`, `Dockerfile`
  - Исключает: `.gitignore`, `.venv/**`, файлы из ignore

**Паттерн**:
```python
(root / "app.py").write_text("print('hi')", encoding="utf-8")
(root / ".venv/lib/python3.10/site-packages/inside.py").mkdir(parents=True)
result = scan_source(str(root))
paths = {f["path"] for f in result.files}
```

### `tests/test_changes.py`

**Класс**: `ChangesTests`

**Тесты**:
- `test_format_changes_md` — проверка генерации Markdown:
  - Секции: "Добавленные файлы", "Изменённые файлы"
  - Перегенерированные разделы
  - Краткое резюме

**Паттерн**:
```python
md = format_changes_md(added, modified, deleted, regenerated, summary)
self.assertIn("Добавленные файлы", md)
```

## Running Tests

```bash
# Запуск всех тестов
python -m unittest discover -s tests

# Запуск конкретного файла
python -m unittest tests/test_cache.py

# Запуск конкретного теста
python -m unittest tests.test_cache.CacheManagerTests.test_diff_files
```

## Test Coverage Gaps

**Не покрыто**:
- `ai_docs/llm.py` — LLMClient (требует моки API)
- `ai_docs/generator*.py` — оркестрация генерации
- `ai_docs/summary.py` — summarization logic
- `ai_docs/domain.py` — detect_domains, classify_type
- `ai_docs/utils.py` — утилиты (sha256_text, is_binary_file)
- `ai_docs/tokenizer.py` — chunk_text, count_tokens

**Ограничения**:
- Нет интеграционных тестов с реальным LLM
- Нет тестов для `generator_sections.py`, `generator_output.py`
- Нет fixtures для сложных сценариев сканирования

## Test Infrastructure

| Dependency | Purpose |
|------------|---------|
| `unittest` | Тест-фреймворк (stdlib) |
| `tempfile.TemporaryDirectory` | Изоляция тестов |
| `pathlib.Path` | Работа с путями |

## Quality Metrics

| Metric | Value |
|--------|-------|
| Test files | 3 |
| Test classes | 3 |
| Test methods | 3 |
| Coverage (estimated) | ~15-20% |
| Mock usage | None (тесты локальные) |
