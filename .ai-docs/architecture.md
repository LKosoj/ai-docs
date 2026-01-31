# Архитектура

```mermaid
graph TD
    A[CLI: ai_docs] --> B[scan_source]
    B --> C{Источник}
    C -->|Локальный путь| D[Сканирование директории]
    C -->|Git URL| E[Клонирование репозитория]
    D --> F[Фильтрация файлов]
    E --> F
    F --> G[.gitignore, .build_ignore]
    F --> H[include/exclude паттерны]
    F --> I[Определение типа: classify_type]
    F --> J[Определение доменов: detect_domains]
    G --> K[ScanResult]
    H --> K
    I --> K
    J --> K
    K --> L[CacheManager]
    L --> M{Изменения?}
    M -->|Нет| N[Использовать кэш]
    M -->|Да| O[Обработка через LLMClient]
    O --> P[chunk_text по max_tokens]
    P --> Q[summarize_file]
    Q --> R[Кэширование ответа: LLMClient.chat]
    R --> S[Сохранение в .ai-docs/]
    L --> T[diff_files: added/modified/deleted]
    T --> U[format_changes_md]
    U --> V[.ai-docs/changes.md]
    Q --> W[Генерация модулей]
    W --> X[build_mkdocs_yaml]
    X --> Y[mkdocs.yml]
    S --> Y
    Y --> Z[write_docs_files]
    Z --> AA[ai_docs_site/ (MkDocs build)]
    A --> AB[Переменные окружения]
    AB --> AC[OPENAI_API_KEY, MODEL, URL]
    AB --> AD[AI_DOCS_THREADS, LOCAL_SITE]
    style A fill:#4CAF50,stroke:#388E3C
    style AA fill:#2196F3,stroke:#1976D2
    style AB fill:#FFC107,stroke:#FFA000
```

## Архитектура

### Обзор
Система `ai_docs` построена по модульной архитектуре, где каждый компонент отвечает за определённый этап генерации документации: сканирование, анализ, генерация, кэширование и публикация. Процесс полностью автоматизирован и поддерживает инкрементальную обработку.

### Основные компоненты

#### 1. **CLI-интерфейс (`ai_docs.cli`)**
Точка входа. Парсит аргументы командной строки, инициализирует настройки из `.env` и запускает основной цикл генерации. Поддерживает режимы `--readme` и `--mkdocs`.

#### 2. **Сканер (`ai_docs.scanner`)**
- Сканирует локальные или удалённые (Git) репозитории.
- Применяет фильтры: `DEFAULT_INCLUDE_PATTERNS`, `DEFAULT_EXCLUDE_PATTERNS`, `.gitignore`, `.build_ignore`.
- Определяет тип файла (`classify_type`) и домены (`detect_domains`).
- Пропускает бинарные файлы и символические ссылки.
- Возвращает `ScanResult` — список файлов с метаданными.

#### 3. **Кэш (`ai_docs.cache`)**
- `CacheManager` управляет двумя кэшами:
  - `index.json`: хранит хеши файлов для определения изменений.
  - `llm_cache.json`: кэширует ответы LLM по хешу запроса.
- `diff_files()` возвращает `added`, `modified`, `deleted`, `unchanged` — позволяет избежать повторной обработки.

#### 4. **LLM-клиент (`ai_docs.llm`)**
- `LLMClient` отправляет запросы к OpenAI-совместимому API.
- Поддерживает кэширование через `threading.Lock`.
- Использует `requests` с таймаутами (30с/120с).
- Параметры: `temperature=0.2`, `max_tokens=1200`, `context_limit=8192`.

#### 5. **Генератор документации (`ai_docs.generator`)**
- `summarize_file()`:
  - Разбивает текст на чанки (`chunk_text`).
  - Формирует промпт с учётом `file_type` и `domains`.
  - При `detailed=True` применяет Doxygen-форматирование.
- `_normalize_module_summary()` — корректирует формат с помощью LLM.
- Параллельная обработка: `ThreadPoolExecutor` (управляется `--threads`).

#### 6. **MkDocs-интеграция (`ai_docs.mkdocs`)**
- `build_mkdocs_yaml()`:
  - Формирует `mkdocs.yml` с динамической навигацией.
  - Поддерживает локальный режим (`--local-site`): убирает `site_url`, отключает `use_directory_urls`.
  - Включает плагины: `search`, `mermaid2`.
- `write_docs_files()` — сохраняет Markdown-файлы в `.ai-docs/`.

#### 7. **Утилиты**
- `ai_docs.utils`: `sha256_text`, `safe_slug`, `is_binary_file`, `read_text_file`.
- `ai_docs.tokenizer`: `chunk_text()` с использованием `tiktoken`.
- `ai_docs.changes`: `format_changes_md()` — отчёт об изменениях.

### Поток данных
1. CLI → `scan_source()` → `ScanResult`
2. `CacheManager.diff_files()` → определение изменённых файлов
3. Для новых/изменённых файлов: `summarize_file()` → LLM → кэш
4. Генерация `changes.md`, `modules/`, `dependencies.md`
5. Построение `mkdocs.yml` и запись в `.ai-docs/`
6. Сборка сайта: `mkdocs build` → `ai_docs_site/`

### Особенности
- **Инкрементальность**: повторные запуски без изменений завершаются мгновенно.
- **Безопасность**: игнорируются бинарные файлы, некорректная кодировка обрабатывается с `errors="ignore"`.
- **Масштабируемость**: параллельная обработка файлов и разделов.
- **Гибкость**: поддержка кастомных игнор-правил, настройка LLM через `.env`.

### Структура выходных данных
```
.  
├── .ai-docs/               # Сгенерированные Markdown-файлы
│   ├── changes.md
│   ├── modules/
│   └── index.md
├── mkdocs.yml              # Конфиг для MkDocs
├── README.md               # Краткое описание проекта
└── ai_docs_site/           # Собранный статический сайт
```
