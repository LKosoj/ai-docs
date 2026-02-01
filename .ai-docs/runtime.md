# Запуск и окружение

## Установка

Установите пакет через `pip`:

```bash
pip install ai-docs-gen
```

Или локально в режиме разработки:

```bash
pip install -e .
```

Требуется Python ≥ 3.8.

## Переменные окружения

Настройте LLM и поведение инструмента через переменные окружения. Создайте файл `.env` в корне проекта или экспортируйте переменные в shell.

| Переменная               | Назначение                                      | Значение по умолчанию             |
|--------------------------|-------------------------------------------------|-----------------------------------|
| `OPENAI_API_KEY`         | Ключ API для OpenAI или совместимого эндпоинта  | Обязательно                        |
| `OPENAI_BASE_URL`        | Базовый URL API (для локальных моделей)         | `https://api.openai.com/v1`       |
| `OPENAI_MODEL`           | Модель LLM (например, `gpt-4o-mini`)            | `gpt-4o-mini`                     |
| `OPENAI_TEMPERATURE`     | Температура генерации (0.0 — строго, 1.0 — креативно) | `0.2`                         |
| `OPENAI_MAX_TOKENS`      | Максимальное число токенов в ответе             | `1200`                            |
| `OPENAI_CONTEXT_TOKENS`  | Общий лимит контекста модели                    | `8192`                            |
| `AI_DOCS_THREADS`        | Количество потоков для параллельной обработки   | `4`                               |
| `AI_DOCS_LOCAL_SITE`     | Режим локального сайта (без `site_url`)         | `false`                           |

Пример `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
AI_DOCS_THREADS=6
AI_DOCS_LOCAL_SITE=true
```

## Запуск CLI

### Базовый запуск

Генерация `README.md` и сайта MkDocs для локальной директории:

```bash
ai-docs --source .
```

Для удалённого Git-репозитория:

```bash
ai-docs --source https://github.com/user/repo.git
```

### Выбор формата вывода

Только `README.md`:

```bash
ai-docs --source . --readme
```

Только MkDocs-сайт:

```bash
ai-docs --source . --mkdocs
```

### Язык документации

Поддерживается русский (`ru`) и английский (`en`):

```bash
ai-docs --source . --language ru
```

### Фильтрация файлов

Используйте glob-шаблоны:

```bash
ai-docs --source . --include "*.py" --include "src/**" --exclude "tests/**"
```

Ограничение по размеру файла (в байтах):

```bash
ai-docs --source . --max-size 500000
```

### Управление кэшированием

Отключить кэширование LLM-ответов:

```bash
ai-docs --source . --no-cache
```

Принудительная перезапись `README.md`:

```bash
ai-docs --source . --force
```

### Режим отладки

Запуск напрямую через Python (полезно при разработке):

```bash
python -m ai_docs --source . --readme --threads 2
```

## Рабочие директории

- `.ai-docs/` — основной каталог вывода:  
  - `docs/` — Markdown-файлы для MkDocs  
  - `index.md`, `architecture.md`, `dependencies.md` и др.  
  - `_index.json` — навигационный индекс проекта  
  - `changes.md` — отчёт об изменениях

- `.ai_docs_cache/` — кэш:  
  - `index.json` — хэши файлов для инкрементального анализа  
  - `llm_cache.json` — закэшированные ответы LLM

- Временные файлы (при работе с Git) удаляются автоматически.

## Интеграция с MkDocs

После генерации выполните:

```bash
cd .ai-docs
mkdocs serve  # локальный просмотр
mkdocs build  # сборка статики
```

Конфигурация `mkdocs.yml` генерируется автоматически с поддержкой:
- Поиска
- Mermaid-диаграмм (`mkdocs-mermaid2-plugin`)
- Расширенной разметки (`pymdown-extensions`)

При `AI_DOCS_LOCAL_SITE=true` или `--local-site`:
- `site_url` не задаётся
- `use_directory_urls: false` — для корректной работы локально

## Требования к окружению

- Python ≥ 3.8
- `git` — для клонирования репозиториев
- Доступ к OpenAI API или OpenAI-совместимому эндпоинту (например, Ollama, LocalAI)

Убедитесь, что `git` доступен в `PATH`, если используете URL-источники.
