# Документация проекта

## Обзор

`ai_docs` — CLI-инструмент для автоматической генерации технической документации по исходному коду и конфигурационным файлам. Поддерживает анализ локальных директорий, локальных и удалённых Git-репозиториев. На выходе создаётся `README.md` и полноценный MkDocs-сайт с иерархической структурой.

### Ключевые возможности
- Автоматическое определение технологий: Kubernetes, Helm, Terraform, Ansible, Docker, CI/CD.
- Генерация `README.md` и сайта MkDocs.
- Поддержка русского и английского языков.
- Инкрементальная генерация с кэшированием LLM-ответов.
- Многопоточная обработка для ускорения анализа.
- Учёт `.gitignore`, `.build_ignore` и встроенных исключений.

---

## Структура выходных данных

После выполнения генерации создаются следующие артефакты:

| Путь | Назначение |
|------|-----------|
| `README.md` | Краткое описание проекта. Перезаписывается только с флагом `--force`. |
| `.ai-docs/` | Каталог сгенерированных Markdown-страниц. |
| `.ai-docs/changes.md` | Отчёт об изменениях между запусками. |
| `.ai-docs/modules/` | Детальная документация по модулям проекта. |
| `mkdocs.yml` | Конфигурация для сборки сайта. |
| `ai_docs_site/` | Собранный статический сайт документации. |
| `.ai_docs_cache/` | Кэш LLM-ответов и индекс файлов. Ускоряет повторные запуски. |

---

## Настройка через `.env`

Поддерживается конфигурация через переменные окружения:

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192
OPENAI_TEMPERATURE=0.2

AI_DOCS_THREADS=4
AI_DOCS_LOCAL_SITE=false
```

> **Примечание**: Переменные CLI имеют приоритет над `.env`.

---

## CLI-интерфейс

### Основные команды

```bash
ai_docs --source ./my-project --readme --mkdocs --language ru
```

### Ключевые параметры

| Параметр | Описание | По умолчанию |
|---------|--------|-------------|
| `--source` | Путь или URL к репозиторию | — |
| `--readme` | Генерировать `README.md` | `False` |
| `--mkdocs` | Генерировать `mkdocs.yml` и сайт | `False` |
| `--language` | Язык документации (`ru`/`en`) | `ru` |
| `--threads` | Количество потоков | `AI_DOCS_THREADS` |
| `--cache-dir` | Директория кэша | `.ai_docs_cache` |
| `--no-cache` | Отключить кэширование LLM | `False` |
| `--local-site` | Настроить MkDocs для локального просмотра | `False` |
| `--force` | Перезаписать существующий `README.md` | `False` |
| `--include` | Шаблоны включения файлов | См. `DEFAULT_INCLUDE_PATTERNS` |
| `--exclude` | Шаблоны исключения | См. `DEFAULT_EXCLUDE_PATTERNS` |
| `--max-size` | Макс. размер файла (байт) | `200000` |

---

## Фильтрация файлов

Сканирование учитывает:
- `.gitignore`
- `.build_ignore`
- Встроенные исключения: `node_modules`, `.venv`, `.env`, `__pycache__`, и др.

Поддерживаются текстовые файлы с расширениями:
- Код: `.py`, `.js`, `.ts`, `.go`, `.java`, `.rs`, `.rb`, `.php`, `.cs`, `.kt`, `.swift`
- Конфиги: `.yml`, `.yaml`, `.json`, `.toml`, `.ini`, `.cfg`, `.env`
- Документация: `.md`, `.rst`, `.adoc`, `.txt`
- Инфраструктура: `.tf`, `Dockerfile`, `Chart.yaml`, `Jenkinsfile`

Бинарные файлы и символические ссылки пропускаются.

---

## Работа с LLM

### Клиент `LLMClient`

Используется для взаимодействия с API LLM (например, OpenAI). Поддерживает:
- Кэширование по хешу запроса (SHA-256).
- Настройку модели, температуры, лимитов токенов.
- Таймауты: 30с на подключение, 120с на ответ.

### Кэширование

- Кэш хранится в `.ai_docs_cache/llm_cache.json`.
- Ключ — нормализованный JSON-запрос.
- Доступ синхронизирован через `threading.Lock`.

---

## Генерация документации

### `summarize_file()`

Основная функция генерации описания файла:
- Разбивает текст на чанки (до `max_tokens=1800`).
- Формирует промпты (`SUMMARY_PROMPT`, `MODULE_SUMMARY_PROMPT`).
- Учитывает домены (например, `kubernetes`, `terraform`).
- Сохраняет результат в `.ai-docs/`.

### Поддерживаемые домены

Определяются по имени файла, пути и содержимому:
- `docker`: `Dockerfile`, `docker-compose.yml`
- `kubernetes`: `deployment.yaml`, `apiVersion:`, `kind:`
- `helm`: `Chart.yaml`, `/templates/`
- `terraform`: `.tf`, `.tfvars`
- `ansible`: `/roles/`, `/tasks/`
- `ci`: `.github/workflows/`, `Jenkinsfile`

---

## MkDocs-интеграция

### `build_mkdocs_yaml()`

Генерирует `mkdocs.yml` с:
- `docs_dir: .ai-docs`
- `site_dir: ai_docs_site`
- Плагинами: `search`, `mermaid2`
- Расширениями: `pymdownx.superfences`
- Локализованными заголовками (на русском)

### Режим `--local-site`

Модифицирует конфигурацию:
- Убирает `site_url`
- Устанавливает `use_directory_urls: false`

---

## Утилиты

### `utils.py`
- `sha256_text()`, `sha256_bytes()` — хеширование.
- `is_binary_file()` — проверка по наличию нулевых байтов (2048 байт).
- `safe_slug()` — преобразование имён файлов в безопасные слаги.
- `read_text_file()` — чтение с `errors="ignore"`.

### `tokenize.py`
- `count_tokens()` — подсчёт токенов через `tiktoken`.
- `chunk_text()` — разбиение текста на чанки по токенам.

### `cache.py`
- `CacheManager` — управление кэшем:
  - `load_index()`, `save_index()` — индекс файлов.
  - `diff_files()` — сравнение изменений (added/modified/deleted).
  - `load_llm_cache()`, `save_llm_cache()` — работа с кэшем LLM.

---

## Примеры использования

### Генерация README для локального проекта

```bash
ai_docs --source . --readme --language ru --force
```

### Полная документация с MkDocs

```bash
ai_docs --source https://github.com/user/repo.git \
        --mkdocs \
        --language en \
        --threads 8 \
        --local-site
```

### Кастомная фильтрация

```bash
ai_docs --source ./project \
        --include "*.py" \
        --include "config/*.yml" \
        --exclude "tests/*" \
        --max-size 500000 \
        --readme
```

---

## Тестирование

Включены юнит-тесты для:
- `scanner`: проверка фильтрации и сканирования.
- `cache`: валидация `diff_files` и сохранения индекса.
- `changes`: форматирование `changes.md`.

Запуск:
```bash
python -m unittest discover tests/
```
