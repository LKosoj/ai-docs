# Документация проекта

## Обзор

`ai_docs` — это CLI-инструмент для автоматической генерации технической документации на основе исходного кода и конфигурационных файлов. Поддерживает анализ локальных директорий, Git-репозиториев (локальных и удалённых) и генерацию:

- `README.md` — краткого описания проекта;
- полноценного сайта документации через MkDocs.

Инструмент использует LLM для анализа структуры проекта, определения ключевых технологий (Kubernetes, Helm, Terraform, Ansible, Docker, CI/CD), суммаризации файлов и генерации структурированной документации. Включает поддержку кэширования, инкрементального обновления, многопоточной обработки и фильтрации по `.gitignore`.

---

## Структура проекта

После выполнения генерации создаются следующие сущности:

| Путь | Назначение |
|------|------------|
| `README.md` | Краткое описание проекта, генерируется при флаге `--readme`. |
| `.ai-docs/` | Директория с Markdown-файлами документации. |
| `.ai-docs/changes.md` | Отчёт об изменениях с момента последнего запуска. |
| `mkdocs.yml` | Конфигурация сайта документации. |
| `ai_docs_site/` | Собранный статический сайт (результат `mkdocs build`). |
| `.ai_docs_cache/` | Кэш LLM-ответов и индекс файлов для ускорения повторных запусков. |

---

## Конфигурация

### Через `.env`

Поддерживается загрузка параметров из `.env`-файла:

```env
# Обязательно
OPENAI_API_KEY=sk-...

# Опционально
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192
OPENAI_TEMPERATURE=0.2

# Параллелизм и поведение
AI_DOCS_THREADS=4
AI_DOCS_LOCAL_SITE=true
```

---

## CLI-интерфейс

### Основные команды

```bash
ai_docs --source ./my-project --readme --mkdocs --language ru
```

### Ключевые параметры

| Параметр | Описание |
|---------|--------|
| `--source PATH_OR_URL` | Путь к локальной директории или URL Git-репозитория (например, `https://github.com/org/repo.git`). |
| `--readme` | Генерировать `README.md`. |
| `--mkdocs` | Генерировать `mkdocs.yml` и структуру документации. |
| `--language ru\|en` | Язык документации (по умолчанию `ru`). |
| `--threads N` | Количество потоков обработки (по умолчанию — из `AI_DOCS_THREADS`). |
| `--cache-dir DIR` | Кастомная директория кэша (по умолчанию `.ai_docs_cache`). |
| `--no-cache` | Отключить кэширование LLM-ответов. |
| `--local-site` | Настроить `mkdocs.yml` для локального хостинга (`site_url: ""`, `use_directory_urls: false`). |
| `--force` | Перезаписать существующий `README.md`. |
| `--include PATTERN` | Дополнительные шаблоны включения файлов (переопределяют стандартные). |
| `--exclude PATTERN` | Шаблоны исключения файлов. |
| `--max-size N` | Максимальный размер файла в байтах (по умолчанию 200 КБ). |

---

## Фильтрация файлов

### Включение по умолчанию (`DEFAULT_INCLUDE_PATTERNS`)
- Исходный код: `*.py`, `*.js`, `*.go` и др.
- Конфигурации: `*.yml`, `*.json`, `*.toml`.
- Документация: `*.md`, `*.rst`.
- Docker, CI/CD: `Dockerfile`, `.gitlab-ci.yml`, `Jenkinsfile`.
- Lock-файлы: `package-lock.json`, `poetry.lock`.

### Исключение по умолчанию (`DEFAULT_EXCLUDE_PATTERNS`)
- `.git/`, `.venv/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`
- Директории MkDocs: `.ai-docs/`, `ai_docs_site/`

> **Примечание**: `.gitignore` учитывается автоматически. Символические ссылки игнорируются.

---

## Архитектура модулей

### `ai_docs.scanner`
Сканирует файлы проекта с фильтрацией.

- **Основные функции**:
  - `scan_source()` — точка входа: обрабатывает URL или путь.
  - `_scan_directory()` — рекурсивный обход с фильтрацией.
  - `_clone_repo()` — клонирует Git-репозиторий во временную директорию.
- **Фильтрация**:
  - Использует `.gitignore` и пользовательские `include`/`exclude`.
  - Пропускает бинарные файлы (`is_binary_file()`).
  - Ограничивает размер файлов (`--max-size`).
- **Результат**: `ScanResult` — список файлов, типы, домены, источник.

---

### `ai_docs.llm`
Клиент для взаимодействия с LLM.

- **Класс**: `LLMClient`
- **Инициализация**:
  ```python
  client = LLMClient(
      api_key="...",
      base_url="https://api.openai.com/v1",
      model="gpt-4o-mini",
      temperature=0.2,
      max_tokens=1200,
      context_limit=8192
  )
  ```
- **Методы**:
  - `chat(messages, cache=None)` — отправка запроса с кэшированием.
  - `_cache_key(payload)` — генерация SHA-256 хеша от нормализованного JSON.
- **Кэширование**:
  - Потокобезопасно через `threading.Lock`.
  - Ключ — хеш от отсортированного JSON-запроса.

---

### `ai_docs.summarizer`
Генерация кратких описаний файлов.

- **Функция**: `summarize_file(content, file_type, domains, llm_client, model)`
- **Логика**:
  - Разбивает текст на чанки (`chunk_text`) с учётом `max_tokens`.
  - Формирует промпт с контекстом (тип, домены).
  - Объединяет ответы LLM в итоговое резюме.
- **Сохранение**: `write_summary(path, content)` — в `.ai-docs/` с безопасным именем (`safe_slug`).

---

### `ai_docs.generator`
Основной модуль генерации документации.

- **Ключевые функции**:
  - `_collect_dependencies()` — извлекает зависимости из `requirements.txt`, `package.json` и др.
  - `_generate_section()` — генерирует раздел с поддержкой Mermaid-диаграмм.
  - `_generate_readme()` — создаёт краткий `README.md`.
  - `generate_docs()` — основной цикл: дифф → суммаризация → генерация → запись.
- **Очистка**: удаляет устаревшие `.md`-файлы, не вошедшие в новую структуру.

---

### `ai_docs.config`
Генерация `mkdocs.yml` и запись файлов.

- **`build_mkdocs_yaml`**:
  - Формирует `mkdocs.yml` с:
    - `site_name`
    - `nav` — структура навигации (условно: "Архитектура", "Запуск", "Конфиги")
    - `docs_dir`, `site_dir`
    - Плагины: `search`, `mermaid2`
    - Markdown-расширения: `pymdownx.superfences`
    - Настройки для `--local-site`
- **`write_docs_files`**:
  - Записывает `.md`-файлы в `docs_dir`, создавая поддиректории.

---

### `ai_docs.cache`
Управление кэшем и отслеживание изменений.

- **Файлы**:
  - `.ai_docs_cache/index.json` — хэши файлов и метаданные.
  - `.ai_docs_cache/llm_cache.json` — закэшированные ответы LLM.
- **Методы**:
  - `load_index()`, `save_index()` — работа с индексом.
  - `diff_files(current_files)` — возвращает `added`, `modified`, `deleted`, `unchanged`.
- **Использование**: оптимизация перегенерации, отчёт в `changes.md`.

---

### `ai_docs.changes`
Формирование отчёта об изменениях.

- **Функция**: `format_changes_md(added, modified, deleted, regenerated_sections, summary)`
- **Формат**:
  ```markdown
  ## Добавленные файлы
  - src/main.py
  - Dockerfile

  ## Изменённые файлы
  - config.yml

  ## Перегенерированные разделы
  - Архитектура
  - Зависимости

  ## Краткое резюме
  Обновлена структура, добавлен Docker.
  ```

---

### `ai_docs.utils`
Вспомогательные утилиты.

| Функция | Назначение |
|--------|-----------|
| `sha256_text(text)` | Хеш строки в UTF-8. |
| `safe_slug(path)` | Преобразует путь в безопасное имя файла. |
| `is_binary_file(path)` | Проверка бинарного файла (по нулевым байтам в первых 2048 байтах). |
| `to_posix(path)` | Преобразует путь в POSIX-формат. |
| `ensure_dir(path)` | Создаёт директорию, если не существует. |
| `read_text_file(path)` | Читает файл с `errors="ignore"`. |

---

### `ai_docs.types`
Классификация файлов и доменов.

- **`classify_type(path)`** → `code`, `docs`, `config`, `infra`, `ci`, `data`, `other`
- **`detect_domains(path, content_snippet)`** → `docker`, `kubernetes`, `terraform`, `helm`, `ansible`, `ci`
- **`is_infra(domains)`** — проверяет, относится ли файл к инфраструктуре.

---

## Процесс генерации

1. **Сканирование** (`scanner.scan_source`)
   - Определяет список файлов с учётом `.gitignore`, `include`, `exclude`, размера.
2. **Классификация** (`types.classify_type`, `detect_domains`)
   - Назначает тип и домены каждому файлу.
3. **Сравнение с кэшом** (`cache.diff_files`)
   - Определяет, какие файлы изменились.
4. **Суммаризация** (`summarizer.summarize_file`)
   - Генерирует краткие описания для новых/изменённых файлов.
5. **Генерация документации** (`generator.generate_docs`)
   - Создаёт разделы: обзор, архитектура, зависимости, запуск.
   - Генерирует `README.md` и `mkdocs.yml`.
6. **Запись и сборка**
   - Сохраняет `.md`-файлы в `.ai-docs/`.
   - Собирает сайт: `mkdocs build`.
7. **Отчёт** (`changes.format_changes_md`)
   - Формирует `changes.md` с детализацией изменений.

---

## Тестирование

- `test_scanner.py` — проверка корректности сканирования и фильтрации.
- `test_cache.py` — тестирование `diff_files` и сохранения индекса.
- `test_changes.py` — валидация формата `changes.md`.

Используются `unittest` и `tempfile` для изолированного тестирования.

---

## Запуск

```bash
# Установка
pip install ai_docs

# Генерация README и сайта
ai_docs --source . --readme --mkdocs --language ru

# С локальным MkDocs
ai_docs --source https://github.com/org/repo.git --mkdocs --local-site

# С кастомными настройками
ai_docs --source ./project --readme --threads 8 --max-size 500000 --exclude "*.log"
```

> **Примечание**: временные директории для Git-репозиториев удаляются автоматически.
