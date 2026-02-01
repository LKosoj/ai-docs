# Архитектура

```mermaid
graph TD
    A[Источник: локальный путь или Git-URL] --> B[Модуль сканирования файлов]
    B --> C[Фильтрация: include/exclude, max_size, .gitignore]
    C --> D[Определение типа файла и домена]
    D --> E[Результат сканирования: ScanResult]
    E --> F[CacheManager: сравнение с кэшем]
    F --> G[Добавленные/изменённые файлы]
    F --> H[Неизменённые файлы (из кэша)]
    G --> I[Параллельная обработка через ThreadPoolExecutor]
    I --> J[summarize_file: генерация описания]
    J --> K[LLMClient: запрос к модели]
    K --> L[Кэширование ответа по хешу payload]
    L --> M[Сохранение в .ai_docs_cache/llm_cache.json]
    J --> N[write_summary: запись в .ai-docs/modules/]
    N --> O[Построение _index.json]
    O --> P[build_mkdocs_yaml: генерация mkdocs.yml]
    P --> Q[Запись docs/index.md и разделов]
    Q --> R[Генерация README.md (опционально)]
    Q --> S[Сборка MkDocs-сайта в ai_docs_site/]
    F --> T[format_changes_md: отчёт в docs/changes.md]
    style A fill:#4C9,stroke:#333
    style R fill:#5C5,stroke:#333
    style S fill:#5C5,stroke:#333
    style T fill:#9C3,stroke:#333
```

# Архитектура

Архитектура `ai_docs` построена вокруг модульного, инкрементального анализа исходного кода с использованием LLM. Система оптимизирована для повторных запусков, поддерживает кэширование, параллельную обработку и интеграцию в CI/CD.

## Основные компоненты

### 1. **Сканирование файлов**
- Вход: локальный путь или URL Git-репозитория.
- Логика: рекурсивный обход с применением фильтров.
- Фильтрация:
  - Включение: `FIXED_INCLUDE_PATTERNS` (Dockerfile, terraform.tf, .github/workflows и др.).
  - Исключение: `.git`, `__pycache__`, `node_modules`, виртуальные окружения, шаблоны из `.gitignore`, `.build_ignore`, `exclude` в `.ai-docs.yaml`.
  - Ограничение по размеру: `--max-size` (по умолчанию 200 000 байт).
- Результат: `ScanResult` с метаданными (путь, тип, домен, хеш).

### 2. **Кэширование и отслеживание изменений**
- `CacheManager` управляет двумя файлами:
  - `.ai_docs_cache/index.json` — хранит хеши и метаданные файлов.
  - `.ai_docs_cache/llm_cache.json` — кэш ответов LLM (ключ — SHA256 от payload).
- На каждом запуске выполняется `diff_files`, возвращающий:
  - `added`, `modified`, `deleted`, `unchanged`.
- Неизменённые файлы пропускают обработку LLM.

### 3. **Генерация документации**
- `summarize_file`:
  - Принимает содержимое, тип, домены, флаг `detailed`.
  - Использует `LLMClient` для запроса.
  - Для `detailed=True` применяет Doxygen-подобный шаблон.
- `_normalize_module_summary` — постобработка: приведение к строгому формату, удаление лишних Markdown-блоков.
- Параллельная обработка: `ThreadPoolExecutor` с числом потоков `--threads` (по умолчанию `AI_DOCS_THREADS` или 4).

### 4. **LLM-клиент**
- `LLMClient`:
  - Поддерживает OpenAI-совместимые API.
  - Параметры: `model`, `temperature`, `max_tokens`, `context_limit`.
  - Автоформирование URL: `/v1/chat/completions`.
  - Кэширование: потокобезопасное, через `threading.Lock`.
  - Таймауты: 120s connect, 480s read.

### 5. **Формирование выходных артефактов**
- `.ai-docs/` — корневая директория документации:
  - `modules/` — Markdown-файлы с описаниями модулей.
  - `_index.json` — навигационный индекс (приоритеты, связи).
  - `index.md`, `architecture.md`, `dependencies.md` — системные разделы.
- `mkdocs.yml`:
  - Генерируется `build_mkdocs_yaml`.
  - Поддерживает `local_site` режим (для `mkdocs serve`).
  - Включает `search`, `mermaid2`, `markdown.extensions.admonition`.
- `ai_docs_site/` — результат `mkdocs build`.
- `README.md` — краткий обзор (генерируется при `--readme` или отсутствии `--mkdocs`).

### 6. **Отчёт об изменениях**
- `format_changes_md`:
  - Формирует `docs/changes.md`.
  - Содержит: добавленные/изменённые/удалённые файлы, перегенерированные разделы, итог.
  - Используется для аудита и CI-логов.

## Поток выполнения

1. **Инициализация**:
   - Парсинг аргументов (`--source`, `--language`, `--threads` и др.).
   - Загрузка `.env`, инициализация `LLMClient.from_env`.
   - Создание `.ai_docs_cache/` при необходимости.

2. **Сканирование**:
   - Клонирование (если URL) → `scan_source`.
   - Загрузка `.ai-docs.yaml` (кастомизация расширений, исключений).
   - Формирование `ScanResult`.

3. **Сравнение с кэшем**:
   - `CacheManager.diff_files` → категории файлов.

4. **Обработка**:
   - Только `added` и `modified` → `summarize_file` в потоках.
   - Результаты сохраняются в `.ai-docs/modules/`.

5. **Построение структуры**:
   - Генерация `_index.json`.
   - Сборка `index.md`, `dependencies.md`, `architecture.md`.
   - `build_mkdocs_yaml` → `mkdocs.yml`.

6. **Финализация**:
   - Запись `README.md` (если нужно).
   - Формирование `changes.md`.
   - Очистка временных директорий (при работе с URL).

## Интеграция и развертывание

- **CI/CD**: поддерживает повторные запуски, кэширование между сборками.
- **Локальный запуск**: `python -m ai_docs --source . --mkdocs --readme`.
- **Ошибки**: логируются, но не прерывают процесс (отказоустойчивость).
- **Язык**: задаётся через `--language` (ru/en), влияет на промпты и заголовки.

Архитектура обеспечивает баланс между скоростью (кэширование, потоки), точностью (фильтрация, домены) и гибкостью (конфигурация, LLM-настройки).
