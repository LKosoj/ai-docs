# Архитектура

```mermaid
graph TD
    A[CLI: ai-docs] --> B[main.py]
    B --> C[scan_source]
    C --> D[Scanner]
    D --> E[Фильтрация: .gitignore, .ai-docs.yaml, exclude]
    D --> F[Распознавание доменов: Kubernetes, Terraform, Docker и др.]
    D --> G[ScanResult: файлы, метаданные, контекст]

    B --> H[CacheManager]
    H --> I[.ai_docs_cache/index.json]
    H --> J[.ai_docs_cache/llm_cache.json]
    H --> K[diff_files: added, modified, deleted]

    B --> L[LLMClient]
    L --> M[OpenAI API / совместимый эндпоинт]
    L --> N[Кэширование по SHA256(payload)]
    L --> O[Потокобезопасность]

    B --> P[summarize_file]
    P --> Q[chunk_text по токенам]
    P --> R[Промпты: SUMMARY, MODULE, CONFIG]
    P --> S[Нормализация вывода]

    B --> T[generate_docs]
    T --> U[write_docs_files]
    U --> V[.ai-docs/modules/]
    U --> W[.ai-docs/configs/]
    U --> X[.ai-docs/dependencies.md, changes.md и др.]

    T --> Y[build_mkdocs_yaml]
    Y --> Z[mkdocs.yml]
    Z --> AA[MkDocs Build]
    AA --> AB[Сайт документации]

    T --> AC[write_readme]
    AC --> AD[README.md]

    style A fill:#4CAF50,stroke:#388E3C
    style M fill:#2196F3,stroke:#1976D2
    style AB fill:#FFC107,stroke:#FFA000
    style AD fill:#FFC107,stroke:#FFA000
```

# Архитектура

Архитектура `ai_docs` построена вокруг модульного CLI-движка, обеспечивающего автоматическую генерацию технической документации на основе анализа кодовой базы с использованием LLM. Система оптимизирована для повторного запуска за счёт инкрементальной обработки и кэширования.

## Основные компоненты

### 1. **CLI-интерфейс (`cli.py`, `main.py`)**
Точка входа. Парсит аргументы командной строки:
- `--source`: путь или URL репозитория.
- `--readme`, `--mkdocs`: выбор формата вывода.
- `--threads`, `--no-cache`, `--force`: управление производительностью и кэшированием.

Запускает последовательность: сканирование → сравнение с кэшем → генерация → вывод.

### 2. **Сканирование (`scanner.py`)**
Рекурсивно обходит файлы, применяя фильтры:
- Учёт `.gitignore`, `.build_ignore`.
- Пользовательские правила из `.ai-docs.yaml`.
- Исключение бинарных, симлинков, файлов >200 КБ.
- Включение по `FIXED_INCLUDE_PATTERNS` (Dockerfile, *.tf и др.).

Результат — `ScanResult` с содержимым первых 4000 символов каждого файла, типом и доменами.

### 3. **Классификация и домены**
На основе `file_extensions.py`:
- `CODE_EXTENSIONS`, `CONFIG_EXTENSIONS`, `DOC_EXTENSIONS`.
- `detect_domains` определяет технологический стек: Kubernetes, Terraform, CI/CD и др.

Используется для выбора промптов и структуры документации.

### 4. **Кэширование (`cache.py`)**
Два уровня:
- **Файловый кэш**: `index.json` хранит хэши (SHA-256) файлов, размеры, временные метки. Используется для `diff_files`.
- **LLM-кэш**: `llm_cache.json` хранит ответы по хешу сериализованного payload. Потокобезопасен.

При запуске `diff_files` возвращает `added`, `modified`, `deleted`, `unchanged` — основа для инкрементальной генерации.

### 5. **LLM-обработка (`llm.py`, `summary.py`)**
- `LLMClient` отправляет запросы в OpenAI-совместимые API.
- `summarize_file` разбивает текст через `chunk_text` (на основе `tiktoken`), применяет промпты:
  - `SUMMARY_PROMPT` — общее описание.
  - `MODULE_SUMMARY_PROMPT` — для кода.
  - `CONFIG_SUMMARY_PROMPT` — для конфигов.
- Вывод нормализуется: удаляются маркеры, форматируется YAML/JSON.

Кэширование LLM-ответов снижает стоимость и время при перезапуске.

### 6. **Генерация документации (`docs.py`)**
Формирует:
- `README.md`: краткое описание проекта, зависимости, команды запуска.
- MkDocs-сайт: `index.md`, `modules/`, `configs/`, `dependencies.md`, `changes.md`.

Использует `build_mkdocs_yaml` для генерации `mkdocs.yml` с:
- Плагином `mermaid2`.
- Древовидной навигацией из `_index.json`.
- Кастомным `Dumper` для корректного экранирования.

### 7. **Вывод и сборка**
- `write_docs_files` сохраняет Markdown в `.ai-docs/`.
- При `--mkdocs`: запускается `mkdocs build -f mkdocs.yml`.
- Если `AI_DOCS_LOCAL_SITE`, сайт не публикуется.

## Поток данных

1. CLI → `scan_source` → `Scanner` → `ScanResult`.
2. `CacheManager.diff_files` → определение изменённых файлов.
3. Для новых/изменённых файлов → `summarize_file` → `LLMClient` → кэш или API.
4. Сборка контекста: зависимости, домены, тестовые команды.
5. Генерация `README.md` и MkDocs-файлов.
6. Запись в `.ai-docs/`, обновление `index.json`, `llm_cache.json`.
7. Формирование `changes.md` через `format_changes_md`.
8. Сборка сайта (если `--mkdocs`).

## Особенности реализации

- **Безопасность путей**: все пути нормализуются в POSIX-формат.
- **Поддержка URL**: временные директории при клонировании удаляются.
- **Локализация**: `SECTION_TITLES`, `DOMAIN_TITLES` поддерживают `ru`, `en`.
- **Ошибки**: накапливаются, выводятся в конце; прогресс логируется.

Архитектура обеспечивает масштабируемость, воспроизводимость и минимальное время повторной генерации за счёт точечной обработки изменений.
