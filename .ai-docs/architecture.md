# Архитектура

```mermaid
graph TD
    A[CLI: ai_docs] --> B[scan_source]
    B --> C[Определение источника: локальный путь / URL]
    C --> D[Клонирование репозитория (если URL)]
    D --> E[_scan_directory]
    E --> F[Фильтрация файлов]
    F --> G[Учёт .gitignore, .build_ignore]
    F --> H[Проверка: размер, бинарные файлы]
    F --> I[Применение include/exclude]
    F --> J[Определение типа: код, конфиг, документация]
    F --> K[Определение домена: Kubernetes, Terraform и др.]
    J --> L[ScanResult]
    K --> L
    L --> M[generate_docs]
    M --> N[Сравнение с кэшем: CacheManager.diff_files]
    N --> O[Файлы: added, modified, deleted, unchanged]
    O --> P[Параллельная обработка: threads]
    P --> Q[summarize_file]
    Q --> R[LLMClient.chat]
    R --> S[Кэширование ответа: llm_cache]
    S --> T[Нормализация: _normalize_module_summary]
    T --> U[Запись в .ai-docs/modules/]
    U --> V[build_mkdocs_yaml]
    V --> W[Генерация mkdocs.yml]
    W --> X[write_docs_files]
    X --> Y[Сборка MkDocs-сайта]
    X --> Z[Генерация README.md]
    N --> AA[format_changes_md]
    AA --> AB[Запись docs/changes.md]
    M --> AC[Обновление .ai_docs_cache/index.json]
```

# Архитектура

Архитектура `ai_docs` построена вокруг модульного, потокового анализа кодовой базы с использованием LLM для генерации технической документации. Система оптимизирована для повторных запусков, поддерживает инкрементальную обработку и интеграцию в CI/CD.

## Основные компоненты

### 1. **CLI-интерфейс (`main.py`, `__main__.py`)**
Точка входа. Обрабатывает аргументы командной строки:
- `--source`: путь или URL репозитория.
- `--readme`, `--mkdocs`: выбор артефактов.
- `--threads`, `--language`, `--include`, `--exclude` — настройки обработки.
- Поддерживает `.env` через `python-dotenv`.

### 2. **Сканер (`scanner.py`)**
Рекурсивно обходит файловую систему:
- Использует `FIXED_INCLUDE_PATTERNS` для инфраструктурных файлов (`.tf`, `Dockerfile`, `.yaml` в `k8s/` и т.д.).
- Применяет `DEFAULT_EXCLUDE_PATTERNS`: `node_modules`, `.venv`, `__pycache__`, скрытые директории.
- Учитывает `.gitignore` и `.build_ignore`.
- Фильтрует по `--max-size` (по умолчанию 200 КБ).
- Определяет тип файла через `classify_type` и домены через `detect_domains`.
- Результат — `ScanResult` с путями, типами, доменами.

### 3. **Кэширование (`cache.py`)**
Два уровня кэша:
- **`index.json`**: хранит хэши файлов (SHA-256), путь, тип. Используется для определения изменений.
- **`llm_cache.json`**: ключ — SHA256 от payload запроса, значение — ответ LLM.
- `CacheManager.diff_files()` возвращает:
  - `added`, `modified`, `deleted`, `unchanged`.
- Кэш сохраняется после ключевых операций для устойчивости к сбоям.

### 4. **LLM-клиент (`llm.py`)**
HTTP-клиент для OpenAI-совместимых API:
- Инициализация через `from_env()` с переменными:
  - `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`.
- Поддержка кастомных `base_url` (например, для локальных моделей).
- Кэширование с `threading.Lock` для потокобезопасности.
- Таймауты: 120s connect, 480s read.

### 5. **Суммаризация (`summarizer.py`)**
Генерация описаний:
- `summarize_file()`:
  - Для `detailed=False` — краткое описание по `SUMMARY_PROMPT`.
  - Для `detailed=True` — Doxygen-стиль по `MODULE_SUMMARY_PROMPT`.
- Повторная нормализация через `_normalize_module_summary`, если LLM нарушает формат.
- Вход: содержимое файла, домены, тип. Выход: Markdown.
- Результат сохраняется в `.ai-docs/modules/` через `write_summary()`.

### 6. **Генерация документации (`docs.py`)**
Формирует выходные артефакты:
- `build_mkdocs_yaml()`:
  - Динамическая навигация: `nav` строится из структуры модулей.
  - Поддержка разделов: Архитектура, Запуск, Конфиги, Модули.
  - Если `AI_DOCS_LOCAL_SITE`, то `site_url: /` и `use_directory_urls: false`.
- `write_docs_files()` — запись Markdown-файлов с созданием поддиректорий.

### 7. **Токенизация (`tokenize.py`)**
Подготовка текста к LLM:
- `count_tokens()` — подсчёт токенов через `tiktoken`.
- `chunk_text()` — разбиение на фрагменты по `max_tokens`, с сохранением целостности строк.
- Используется при превышении `OPENAI_CONTEXT_TOKENS`.

### 8. **Вспомогательные модули**
- `utils.py`: `is_binary()`, `safe_read()`, `normalize_path()`, `ensure_dir()`.
- `extensions.py`: классификация по расширениям, именам файлов, путям.
- `changes.py`: `format_changes_md()` — отчёт по изменениям в `docs/changes.md`.

## Поток выполнения

1. **Сканирование**: `scan_source()` → `ScanResult`.
2. **Сравнение с кэшем**: `CacheManager.diff_files()` → списки изменений.
3. **Обработка**:
   - Только `added` и `modified` передаются в `summarize_file()`.
   - Параллельно по `--threads`, с кэшированием LLM-ответов.
4. **Генерация**:
   - Запись модулей в `.ai-docs/modules/`.
   - Построение `_index.json` (навигация).
   - Генерация `README.md` и `mkdocs.yml`.
5. **Сборка**:
   - Запуск `mkdocs build` (если `--mkdocs`).
   - Запись `docs/changes.md`.

## Выходные артефакты

- `.ai-docs/` — детальная документация:
  - `index.md`, `architecture.md`, `dependencies.md`.
  - `modules/` — по одному `.md` на файл.
  - `_index.json` — структура навигации.
- `ai_docs_site/` — собранный MkDocs-сайт.
- `README.md` — краткий обзор проекта.
- `docs/changes.md` — отчёт об изменениях.
- `.ai_docs_cache/` — `index.json`, `llm_cache.json`.

## Особенности

- **Инкрементальность**: неизменённые файлы не перепроцессируются.
- **Безопасность**: бинарные файлы не читаются, текст обрезается до 4000 символов.
- **Гибкость**: `.ai-docs.yaml` позволяет кастомизировать расширения и фильтры.
- **CI/CD-дружелюбность**: переменные окружения, повторяемость, кэширование.

Архитектура обеспечивает баланс между скоростью, точностью и масштабируемостью, позволяя документировать проекты любого размера.
