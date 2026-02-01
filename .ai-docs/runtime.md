# Запуск и окружение

## Переменные окружения

Для работы `ai_docs` требуются следующие переменные окружения:

| Переменная | Назначение | Значение по умолчанию |
|-----------|------------|------------------------|
| `OPENAI_API_KEY` | Ключ для доступа к OpenAI или совместимому API | Обязательна |
| `OPENAI_BASE_URL` | Базовый URL API (поддержка кастомных эндпоинтов) | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Модель LLM для генерации документации | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Уровень креативности генерации | `0.2` |
| `OPENAI_MAX_TOKENS` | Максимальное количество токенов в ответе | `1200` |
| `OPENAI_CONTEXT_TOKENS` | Общий лимит контекста | `8192` |
| `AI_DOCS_THREADS` | Количество потоков для параллельной обработки | `4` |
| `AI_DOCS_LOCAL_SITE` | Включить локальный режим MkDocs (без `mkdocs-material`) | `false` |

Переменные загружаются из `.env`-файла при запуске.

## Установка и запуск

### Установка
```bash
pip install ai-documentery
```

Или из исходников:
```bash
pip install -e .
```

### Базовый запуск
```bash
ai-docs --source /path/to/project --readme --mkdocs
```

### Примеры использования

**Генерация README на русском:**
```bash
ai-docs --source . --readme --language ru --force
```

**Генерация сайта документации с кастомными фильтрами:**
```bash
ai-docs \
  --source https://github.com/user/repo.git \
  --mkdocs \
  --include "*.tf" "charts/**" \
  --exclude "*.log" "tmp/" \
  --threads 8
```

**Запуск без кэширования (для отладки):**
```bash
ai-docs --source . --readme --no-cache
```

## Режимы работы

| Флаг | Назначение |
|------|-----------|
| `--readme` | Генерировать `README.md` |
| `--mkdocs` | Генерировать структуру для MkDocs (`docs/`, `mkdocs.yml`) |
| `--force` | Перезаписать существующий `README.md` |
| `--no-cache` | Отключить кэширование LLM-запросов |
| `--language ru/en` | Язык документации |

## Артефакты и пути

После запуска создаются:

- `README.md` — в корне проекта
- `docs/` — полная документация (если `--mkdocs`)
- `mkdocs.yml` — конфигурация сайта
- `.ai-docs/` — промежуточные файлы документации
- `.ai_docs_cache/` — кэш LLM и хэши файлов
- `ai_docs_site/` — собранный сайт (после `mkdocs build`)

## Ограничения и настройки

- Максимальный размер файла: **200 КБ** (настраивается через `--max-size`)
- Игнорируемые директории: `.git`, `.venv`, `node_modules`, `__pycache__`, `dist`, `build`, `.ai-docs`, `.ai_docs_cache`, `ai_docs_site`
- Поддержка `.gitignore` и `.build_ignore`
- Кастомизация через `.ai-docs.yaml` (расширения, исключения)

## Запуск MkDocs

После генерации:

```bash
mkdocs build -f mkdocs.yml
```

Для локального просмотра:
```bash
mkdocs serve -f mkdocs.yml
```

> **Примечание:** При `AI_DOCS_LOCAL_SITE=true` используется упрощённая конфигурация без `mkdocs-material`.
