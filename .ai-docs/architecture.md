# Архитектура

```mermaid
flowchart TD
    A[CLI: ai_docs] --> B[main.py]
    B --> C{Источник?}
    C -->|Локальный путь| D[scanner.py: scan_source]
    C -->|Git URL| E[scanner.py: _clone_repo]
    D --> F[Фильтрация: .gitignore, .build_ignore]
    E --> F
    F --> G[ScanResult: файлы + метаданные]
    G --> H[cache.py: CacheManager]
    H --> I{Изменения?}
    I -->|Новые/изменённые| J[summarize.py: summarize_file]
    I -->|Без изменений| K[Использовать кэш]
    J --> L[LLMClient: chat()]
    L --> M[tokens.py: chunk_text]
    M --> N[API: OpenAI/GPT]
    N --> O[Кэширование ответа: llm_cache]
    O --> P[write_summary: .ai-docs/]
    K --> P
    P --> Q[docs.py: build_mkdocs_yaml]
    Q --> R[mkdocs.yml]
    P --> S[write_docs_files]
    S --> T[.ai-docs/]
    T --> U[mkdocs build]
    U --> V[ai_docs_site/]
    H --> W[format_changes_md]
    W --> X[.ai-docs/changes.md]
    B --> Y[Завершение: очистка временных репозиториев]

    style A fill:#4B9CD3,stroke:#333
    style V fill:#27AE60,stroke:#333,color:#fff
    style X fill:#F39C12,stroke:#333,color:#fff
```

## Основные компоненты

### 1. **CLI-интерфейс (`main.py`, `__main__.py`)**
Точка входа. Обрабатывает аргументы командной строки, инициализирует окружение, запускает последовательность обработки. Поддерживает:
- `--source` (локальный путь или URL)
- `--readme` / `--mkdocs`
- `--language`, `--threads`, `--cache-dir`, `--force`
- Автоматическое добавление в `sys.path` при прямом запуске.

### 2. **Сканер файлов (`scanner.py`)**
Рекурсивно сканирует директорию или клонирует Git-репозиторий (`--depth 1`). Применяет фильтрацию:
- По умолчанию: включает код, конфиги, документацию.
- Исключает: `node_modules`, `.venv`, `.git`, бинарные файлы.
- Учитывает `.gitignore`, `.build_ignore` через `pathspec`.
- Ограничивает размер файлов (`--max-size`, по умолчанию 200 КБ).
- Возвращает `ScanResult` с метаданными: путь, тип (`classify_type`), домены (`detect_domains`).

### 3. **Кэширование (`cache.py`, `utils.py`)**
- `CacheManager`: управляет `index.json` (хэши файлов) и `llm_cache.json` (ответы LLM).
- `diff_files()`: определяет `added`, `modified`, `deleted`, `unchanged` на основе SHA-256.
- `llm_cache` — потокобезопасный словарь, ключ — хэш нормализованного JSON-запроса.
- Автоматическое создание `.ai_docs_cache/`.

### 4. **LLM-клиент (`llm.py`)**
- `LLMClient`: отправляет запросы к OpenAI-совместимому API.
- Поддерживает: `OPENAI_BASE_URL`, кастомные модели, таймауты.
- Параметры: `temperature=0.2`, `max_tokens=1200`, `context_limit=8192`.
- Кэширование через `threading.Lock`.

### 5. **Генерация документации (`summarize.py`)**
- `summarize_file()`: разбивает текст на чанки (`chunk_text`, до 1800 токенов), отправляет в LLM.
- Использует разные промпты: `SUMMARY_PROMPT` (кратко), `MODULE_SUMMARY_PROMPT` (подробно).
- Дополняет промпт доменами (Kubernetes, Terraform и др.).
- Результат сохраняется в `.ai-docs/` с безопасным именем (`safe_slug`).

### 6. **Построение MkDocs (`docs.py`)**
- `build_mkdocs_yaml()`: генерирует `mkdocs.yml` с:
  - `docs_dir: .ai-docs`
  - `site_dir: ai_docs_site`
  - Плагины: `search`, `mermaid2`
  - Навигация: динамически строится по модулям и секциям.
- При `--local-site`: убирает `site_url`, отключает `use_directory_urls`.
- `write_docs_files()` — безопасная запись Markdown-файлов.

### 7. **Вспомогательные модули**
- `tokens.py`: `count_tokens`, `chunk_text` через `tiktoken`.
- `utils.py`: `sha256_text`, `is_binary_file`, `safe_slug`, `to_posix`.
- `changes.py`: `format_changes_md` — отчёт об изменениях в Markdown.
- `types.py`: `classify_type`, `detect_domains`, `is_infra` — анализ по расширениям и контексту.

## Потоки данных

1. **Инициализация**: CLI → `main.py` → загрузка `.env`, настройка LLM.
2. **Сканирование**: `scan_source` → фильтрация → `ScanResult`.
3. **Сравнение с кэшем**: `CacheManager.diff_files()` → определение изменённых файлов.
4. **Генерация**: `summarize_file` → `LLMClient.chat()` → кэширование → сохранение в `.ai-docs/`.
5. **Сборка**: `build_mkdocs_yaml` + `write_docs_files` → `mkdocs build` → `ai_docs_site/`.
6. **Отчёт**: `format_changes_md` → `changes.md`.

## Особенности реализации

- **Инкрементальная генерация**: перепроцессинг только изменённых файлов.
- **Параллелизм**: `ThreadPoolExecutor` с `--threads` (по умолчанию из `AI_DOCS_THREADS`).
- **Безопасность**: игнорирование бинарных файлов, обрезка по токенам, `errors="ignore"` при чтении UTF-8.
- **Поддержка локализации**: русские заголовки в `SECTION_TITLES`, `DOMAIN_TITLES`.
- **Очистка**: удаление временных репозиториев после обработки URL-источников.
