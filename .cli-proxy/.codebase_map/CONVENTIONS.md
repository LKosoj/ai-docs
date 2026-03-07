# Conventions

## Code Style

| Aspect | Convention |
|--------|------------|
| **Naming** | `snake_case` для функций/переменных, `PascalCase` для классов |
| **Imports** | Стандартные → сторонние → локальные (`. `), с сортировкой |
| **Type hints** | Аннотации типов обязательны для публичных API |
| **Docstrings** | Краткое описание назначения, без форматов Google/NumPy |

## File Organization

```
ai_docs/
├── __main__.py      # Entry point (импорт cli.main)
├── cli.py           # CLI (argparse), точка входа
├── scanner.py       # Сканирование репозитория
├── domain.py        # Доменная логика (расширения, домены)
├── utils.py         # Утилиты (SHA256, file I/O)
├── llm.py           # LLM-клиент (OpenAI API)
├── tokenizer.py     # Подсчёт токенов
├── cache.py         # Менеджер кэша (index.json)
├── generator*.py    # Генерация документации (7 файлов)
└── tests/           # Тесты вне пакета
```

## Naming Patterns

| Pattern | Example |
|---------|---------|
| Private helpers | `_normalize_extensions()`, `_scan_directory()` |
| Public API | `scan_source()`, `generate_docs()`, `from_env()` |
| Async functions | `summarize_*()`, `_generate_docs_async()` |
| Classes | `LLMClient`, `CacheManager`, `ScanResult` |

## Error Handling

- **LLM calls**: retry с exponential backoff (max 5 попыток)
- **File I/O**: `encoding="utf-8", errors="ignore"` для чтения
- **Cache corruption**: fallback на `.bad` файл при JSON decode error

## Logging

- Формат: `[ai-docs] <component>: <message>`
- Примеры:
  ```
  [ai-docs] scan complete: 42 files
  [ai-docs] diff: added=3 modified=5 deleted=1
  [ai-docs] summarize progress: 10/25 (45s)
  [ai-docs] errors summary: <list>
  ```

## Configuration

**Проектный конфиг**: `.ai-docs.yaml`
```yaml
code_extensions:
  .py: Python
  .ts: TypeScript
doc_extensions:
  .md: Markdown
config_extensions:
  .yml: YAML
  .toml: TOML
# exclude: ["logs/*", "**/*.log"]  # опционально
```

**Environment variables**:
| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_BASE_URL` | — | API endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `OPENAI_TEMPERATURE` | `0.2` | Sampling temperature |
| `OPENAI_MAX_TOKENS` | `1200` | Max response tokens |
| `OPENAI_CONTEXT_TOKENS` | `8192` | Context window size |
| `AI_DOCS_THREADS` | `1` | Parallel workers |
| `AI_DOCS_LOCAL_SITE` | `false` | MkDocs local mode |
| `AI_DOCS_REGEN` | — | Force regen sections |

## Async Patterns

- **Semaphore**: `asyncio.Semaphore(threads)` для ограничения параллелизма
- **Lock**: `asyncio.Lock()` для потокобезопасного счёта `done`
- **Gather**: `asyncio.gather(*(run_one(...) for ...))` для параллельного выполнения

## Testing Conventions

- **Фреймворк**: `unittest` (стандартная библиотека)
- **Расположение**: `tests/` вне пакета
- **Именование**: `test_*.py`, классы `*Tests`
- **Запуск**: `python -m unittest discover -s tests`
