# Concerns

## Security

### 🔴 Critical

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/llm.py:32` | `httpx.AsyncClient(verify=False)` — отключена проверка SSL | MITM-атаки при запросах к LLM API |
| `ai_docs/llm.py:104` | API ключ передаётся без валидации | Возможность утечки при ошибочном вводе |

**Recommendation**:
```python
# llm.py
http_client = httpx.AsyncClient(verify=True)  # или путь к CA bundle
```

### 🟡 Major

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/scanner.py:221` | `subprocess.check_call` с git URL без санитизации | Potential command injection при malformed URL |
| `ai_docs/scanner.py:169` | Чтение файлов без ограничений по времени | DoS через большие файлы (max_size только на размер) |

## Reliability

### 🔴 Critical

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/llm.py:88-95` | Retry logic не различает 4xx ошибки | 400/401/403 будут retry'иться 5 раз без пользы |
| `ai_docs/generator.py:145` | `asyncio.run()` внутри `generate_docs()` | Нельзя использовать в async context (nested event loop) |

**Recommendation**:
```python
# generator.py — export async API
async def generate_docs_async(...) -> None:
    await _generate_docs_async(...)

def generate_docs(...) -> None:
    return asyncio.run(_generate_docs_async(...))
```

### 🟡 Major

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/summary.py:157` | `_needs_doxygen_fix()` эвристический | Ложные срабатывания на легитимный Markdown |
| `ai_docs/scanner.py:199` | `content[:4000]` для detect_domains | Потеря контекста для больших файлов |
| `ai_docs/cache.py:47` | `json.JSONDecodeError` → `.bad` файл | Silent corruption при повреждении кэша |
| `ai_docs/llm.py:74` | `timeout = httpx.Timeout(...)` внутри retry | Новый timeout на каждую попытку, но не на всё соединение |

### 🟡 Minor

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/generator.py:138` | `errors: List[str]` передаётся по ссылке | Race condition при параллельных ошибках |
| `ai_docs/generator_summarize.py:33` | `nonlocal done` + `asyncio.Lock` | Избыточная сложность, можно через Queue |
| `ai_docs/scanner.py:159` | `dirnames[:] = [d for d in dirnames if d != ".git"]` | Не исключает другие скрытые директории (.svn, .hg) |

## Maintainability

### 🟡 Major

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/summary.py:12-102` | Prompt templates в коде (400+ строк) | Сложно обновлять, нет версионирования промптов |
| `ai_docs/generator_sections.py:20-36` | Prompt логика внутри `generate_section()` | Hardcoded правила для "архитектура" |
| `ai_docs/mkdocs.py:46-90` | `_build_tree_nav()` — сложная рекурсия | Трудно тестировать, нет unit тестов |

**Recommendation**: Вынести промпты в отдельный модуль `ai_docs/prompts.py` с версионированием.

### 🟡 Minor

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/domain.py:1-80` | Хардкод расширений и маркеров | Дублирование с `scanner.py:FIXED_INCLUDE_PATTERNS` |
| `ai_docs/generator_shared.py:85-105` | `render_testing_section()` — парсинг pyproject.toml | Хрупкая логика, нет обработки poetry vs setuptools |
| `ai_docs/cli.py:44` | `if not args.readme and not args.mkdocs and not args.regen:` | Warning печатается всегда, даже при валидном use case |

## Performance

### 🟡 Major

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/llm.py:40-47` | `_estimate_input_tokens()` считает все сообщения | Overhead для больших контекстов |
| `ai_docs/scanner.py:198` | `read_text_file()` читает весь файл в память | Memory spike для файлов >10MB |
| `ai_docs/generator_cache.py:88` | `cleanup_orphan_summaries()` — O(n²) | Медленно при 1000+ файлов |

### 🟡 Minor

| File | Issue | Impact |
|------|-------|--------|
| `ai_docs/tokenizer.py:14` | `tiktoken.encoding_for_model()` каждый раз | Нет кэширования encoding объекта |
| `ai_docs/generator_summarize.py:24` | `save_cb()` после каждого файла | Частая запись index.json (I/O overhead) |

## Testing Gaps

| Module | Coverage | Missing Tests |
|--------|----------|---------------|
| `ai_docs/llm.py` | 0% | Retry logic, cache, timeout computation |
| `ai_docs/summary.py` | 0% | Prompt formatting, _needs_doxygen_fix, _format_config_blocks |
| `ai_docs/generator*.py` | 0% | Orchestrator logic, diff handling |
| `ai_docs/domain.py` | 0% | detect_domains, classify_type, is_infra |
| `ai_docs/mkdocs.py` | 0% | _build_tree_nav, _insert_nav_node |
| `ai_docs/generator_sections.py` | 0% | generate_section, build_hierarchical_context |

**Total test coverage**: ~15-20% (только cache, scanner, changes)

## Technical Debt

| File | Issue | Priority |
|------|-------|----------|
| `ai_docs/llm.py` | SSL verification disabled | P0 |
| `ai_docs/generator.py` | No async public API | P1 |
| `ai_docs/summary.py` | Prompts in code | P1 |
| `ai_docs/scanner.py` | No unit tests for domain detection | P2 |
| `ai_docs/cache.py` | Silent corruption handling | P2 |
| `ai_docs/tokenizer.py` | No encoding cache | P3 |

## Limitations

| Area | Limitation |
|------|------------|
| **LLM** | Только OpenAI-compatible API (нет Anthropic, Gemini) |
| **Languages** | Генерация только на ru/en (hardcoded prompts) |
| **Chunking** | Фиксированный размер 1800 токенов (нет адаптивности) |
| **Caching** | In-memory lock, нет persistence между запусками |
| **Parallelism** | Semaphore на уровне файлов, не на уровне чанков |
| **Output** | Только MkDocs (нет Sphinx, Docusaurus) |
