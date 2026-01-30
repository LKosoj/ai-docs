# Документация проекта

## Обзор

`ai_docs` — это CLI-инструмент для автоматической генерации технической документации на основе исходного кода и конфигурационных файлов. Поддерживает анализ локальных директорий и Git-репозиториев (включая удалённые), автоматически распознаёт технологические домены: Kubernetes, Helm, Terraform, Ansible, Docker, CI/CD.

После обработки генерирует:
- `README.md` — краткое описание проекта,
- `docs/` — структурированные страницы документации,
- `mkdocs.yml` — конфигурация для MkDocs,
- `ai_docs_site/` — собранный статический сайт,
- `.ai_docs_cache/` — кэш LLM-суммаризаций для инкрементальной обработки.

## Запуск

```bash
ai_docs --source ./my-project --language ru --readme --mkdocs
```

Поддерживается запуск как установленного пакета или через `python -m ai_docs`.

## Основные параметры CLI

| Параметр | Описание | По умолчанию |
|--------|--------|-------------|
| `--source` | Путь к директории или URL Git-репозитория | Обязательный |
| `--output` | Выходная директория | `./output/<repo_name>` |
| `--readme` | Генерировать `README.md` | Включено |
| `--mkdocs` | Генерировать `mkdocs.yml` и `docs/` | Включено |
| `--language` | Язык документации (`ru`/`en`) | `ru` |
| `--include` | Glob-паттерны для включения файлов | См. `DEFAULT_INCLUDE_PATTERNS` |
| `--exclude` | Glob-паттерны для исключения | См. `DEFAULT_EXCLUDE_PATTERNS` |
| `--max-size` | Макс. размер файла (байт) | 200 KB |
| `--threads` | Количество потоков | `AI_DOCS_THREADS` или 4 |
| `--local-site` | Настройка MkDocs для локального просмотра | Отключено |
| `--no-cache` | Отключить кэширование | Отключено |
| `--cache-dir` | Директория кэша | `.ai_docs_cache` |

## Архитектура компонентов

### `scanner.py` — Сканирование файлов
Собирает файлы из указанного источника с учётом:
- `.gitignore` и встроенных шаблонов исключения (`.venv`, `node_modules`, `build`, `dist` и др.),
- фильтрации по `--include`/`--exclude`,
- ограничения по размеру (`--max-size`).

**Ключевые функции:**
- `scan_source()` — точка входа, обрабатывает локальные пути и Git-URL.
- `_clone_repo()` — клонирует репозиторий с `--depth 1`.
- `classify_type()` — определяет тип файла: `code`, `config`, `docs`, `infra`, `ci`, `data`, `other`.
- `detect_domains()` — распознаёт домены: `kubernetes`, `helm`, `terraform`, `ansible`, `docker`, `ci`.
- `is_infra()` — проверяет, относится ли файл к инфраструктуре.

### `llm.py` — Взаимодействие с LLM
Клиент для вызова API языковых моделей с кэшированием.

**Настройки через `.env`:**
```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.2
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192
```

**Ключевые методы:**
- `LLMClient.chat(messages, cache)` — отправка запроса с кэшированием по хешу payload.
- `_cache_key()` — генерация SHA-256 хеша от нормализованного JSON.

Кэширование использует `threading.Lock` для потокобезопасности.

### `summarize.py` — Суммаризация файлов
Генерирует краткие описания содержимого файлов с помощью LLM.

**Процесс:**
1. Разбивает текст на чанки по токенам (`chunk_text`).
2. Формирует промпт с контекстом (тип, домены).
3. Отправляет чанки в LLM.
4. Объединяет ответы в итоговое резюме.
5. Сохраняет в `docs/summaries/` с безопасным именем (`safe_slug`).

Использует кэш для повторных запросов.

### `generate_docs.py` — Генерация документации
Основной модуль, управляющий процессом генерации.

**Функции:**
- `_generate_section()` — создаёт разделы: архитектура, запуск, зависимости, соглашения.
- `_generate_readme()` — формирует `README.md`.
- `_collect_dependencies()` — извлекает зависимости из `requirements.txt`, `package.json`, `pyproject.toml`.
- `_truncate_context()` — ограничивает объём данных для LLM по токенам.

**Особенности:**
- Параллельная обработка через `ThreadPoolExecutor`.
- Удаление устаревших файлов документации.
- Поддержка локализации (`SECTION_TITLES`, `DOMAIN_TITLES`).

### `mkdocs.py` — Генерация MkDocs
Формирует `mkdocs.yml` и структуру `docs/`.

**Функции:**
- `build_mkdocs_yaml()` — возвращает YAML-конфигурацию.
  - При `local_site=True`: `use_directory_urls: false`, `site_url: /`.
  - Автоматически включает разделы: "Архитектура", "Запуск", "Конфиги", "Изменения".
- `write_docs_files()` — записывает Markdown-файлы, создавая промежуточные директории.

### `cache.py` — Управление кэшем
Хранит:
- `index.json` — хэши файлов и статусы.
- `llm_cache.json` — ответы LLM.

**Методы:**
- `diff_files(current_files)` — возвращает `added`, `modified`, `deleted`, `unchanged`.
- `load_index()`, `save_index()` — работа с индексом.
- `load_llm_cache()`, `save_llm_cache()` — работа с кэшем LLM.

Кэширование позволяет пересчитывать только изменённые файлы.

### `utils.py` — Вспомогательные утилиты
- `sha256_text()`, `sha256_bytes()` — хеширование.
- `is_binary_file()` — проверка бинарного файла (по нулевым байтам).
- `read_text_file()` — чтение с `errors="ignore"`.
- `safe_slug()` — преобразование в безопасное имя файла.
- `ensure_dir()` — создание директорий.
- `is_url()` — проверка строки на URL.
- `to_posix()` — нормализация пути.

### `tokenize.py` — Работа с токенами
Использует `tiktoken` для:
- `count_tokens(text, model)` — подсчёт токенов.
- `chunk_text(text, model, max_tokens)` — разбиение на чанки.

Поддерживает модели с `cl100k_base` (GPT-3.5, GPT-4). При неизвестной модели — fallback на `cl100k_base`.

### `changes.py` — Отчёт об изменениях
Формирует `docs/changes.md` через `format_changes_md()`.

**Структура отчёта:**
```markdown
## Добавленные файлы
- docs/new_feature.md

## Изменённые файлы
- docs/architecture.md

## Перегенерированные разделы
- Архитектура
- Зависимости

## Краткое резюме
Обновлены зависимости и добавлена документация по новому модулю.
```

## Интеграция и использование

### В CI/CD
```yaml
- name: Generate Docs
  run: |
    ai_docs --source . --language en --mkdocs --local-site
    mkdocs build --site-dir public
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Локальная разработка
```bash
# Генерация документации с кэшированием
ai_docs --source . --readme --mkdocs --language ru

# Перегенерация без кэша
ai_docs --source . --no-cache

# Только README
ai_docs --source . --mkdocs false
```

### Поддержка технологий
| Технология | Определяется по |
|----------|---------------|
| Kubernetes | `k8s/`, `kubernetes/`, `deployment.yaml`, `apiVersion:`, `kind:` |
| Helm | `Chart.yaml`, `values.yaml`, `/templates/` |
| Terraform | `.tf`, `.tfvars`, `terraform` в пути |
| Ansible | `ansible/`, `/roles/`, `/tasks/` |
| Docker | `Dockerfile`, `docker-compose.yml` |
| CI/CD | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile` |

## Тестирование
- `test_scanner.py` — проверка корректности сканирования с `.gitignore`.
- `test_cache.py` — тест `diff_files()` и управления индексом.
- `test_changes.py` — проверка формата `changes.md`.

Запуск:
```bash
python -m unittest discover tests/
```

## Очистка
После генерации временные директории (при работе с URL) удаляются автоматически. Кэш можно очистить вручную:
```bash
rm -rf .ai_docs_cache/
```
