# Запуск и окружение

## Установка и запуск

Инструмент `ai_docs` доступен как CLI-приложение. Для запуска:

```bash
# Установка (если пакет доступен в PyPI)
pip install ai_docs

# Запуск для локального репозитория
ai_docs --source . --mkdocs --readme --language ru

# Запуск для удалённого репозитория
ai_docs --source https://github.com/user/repo.git --mkdocs
```

Альтернативно, можно запустить напрямую из исходников:
```bash
python -m ai_docs --source .
```

## Требования

- Python 3.9+
- `tiktoken`, `requests`, `pathspec`, `PyYAML`
- Доступ к LLM API (например, OpenAI, Azure OpenAI)

## Переменные окружения (`.env`)

Настройки передаются через `.env` или напрямую в окружении:

```env
# Обязательно
OPENAI_API_KEY=sk-...

# Опционально
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192
OPENAI_TEMPERATURE=0.2

# Параллелизация
AI_DOCS_THREADS=4

# Режим MkDocs
AI_DOCS_LOCAL_SITE=true
```

## Основные CLI-параметры

| Параметр | Назначение |
|--------|-----------|
| `--source PATH_OR_URL` | Путь к директории или URL Git-репозитория |
| `--readme` | Генерировать `README.md` |
| `--mkdocs` | Генерировать `mkdocs.yml` и структуру сайта |
| `--language ru\|en` | Язык документации (по умолчанию: `ru`) |
| `--output DIR` | Каталог вывода (по умолчанию: `./output/<repo>`) |
| `--threads N` | Количество потоков (по умолчанию: `AI_DOCS_THREADS`) |
| `--cache-dir DIR` | Каталог кэша (по умолчанию: `.ai_docs_cache`) |
| `--no-cache` | Отключить кэширование LLM-ответов |
| `--local-site` | Настроить MkDocs для локального просмотра |
| `--force` | Перезаписать существующий `README.md` |
| `--include PATTERN` | Шаблоны включения файлов |
| `--exclude PATTERN` | Шаблоны исключения файлов |
| `--max-size N` | Макс. размер файла в байтах (по умолчанию: 204800) |

## Режимы работы

### 1. Только README
```bash
ai_docs --source . --readme --language ru
```
Создаёт `README.md` в корне проекта.

### 2. Полный MkDocs-сайт
```bash
ai_docs --source . --mkdocs --readme
```
Генерирует:
- `.ai-docs/` — исходники документации
- `mkdocs.yml` — конфигурация
- `ai_docs_site/` — собранный сайт

После генерации сайт можно запустить:
```bash
cd ai_docs_site && python -m http.server 8000
```

### 3. Локальный режим MkDocs
С флагом `--local-site` или переменной `AI_DOCS_LOCAL_SITE=true`:
- Убирается `site_url` из `mkdocs.yml`
- Отключается `use_directory_urls`
- Подходит для просмотра без веб-сервера

## Кэширование

Инструмент использует кэш для ускорения повторных запусков:
- `.ai_docs_cache/index.json` — хеши файлов и статус изменений
- `.ai_docs_cache/llm_cache.json` — ответы LLM по хешу запроса

При неизменённых файлах обработка пропускается, генерация занимает секунды.

Отключить кэш:
```bash
ai_docs --source . --no-cache
```

## Игнорируемые файлы

Автоматически исключаются:
- `node_modules`, `.venv`, `.env`, `__pycache__`
- `.git/`, `.github/`, `.vscode/`
- Бинарные файлы
- Файлы, указанные в `.gitignore` и `.build_ignore`

Кастомизация:
```bash
ai_docs --source . --exclude "*.log" --exclude "temp/"
```

## Ограничения

- Файлы > 200 КБ пропускаются (настраивается через `--max-size`)
- Бинарные файлы не анализируются
- Символические ссылки игнорируются
- Удалённые репозитории клонируются с `--depth 1`
