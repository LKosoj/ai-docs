# Запуск и окружение

## Базовые требования

- Python 3.8 или выше
- Доступ к LLM через OpenAI-совместимое API (например, OpenAI, Azure OpenAI)
- Установленный `mkdocs` (для генерации сайта)

## Установка

```bash
pip install ai-docs-gen
```

Или установка из репозитория:

```bash
git clone https://github.com/your-repo/ai-docs-gen.git
cd ai-docs-gen
pip install -e .
```

## Переменные окружения

Обязательные:

```bash
export OPENAI_API_KEY=your_api_key_here
```

Опциональные (с значениями по умолчанию):

```bash
export OPENAI_BASE_URL=https://api.openai.com/v1  # для сторонних провайдеров
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_MAX_TOKENS=4096
export OPENAI_CONTEXT_TOKENS=32768
export OPENAI_TEMPERATURE=0.3
export AI_DOCS_THREADS=4
export AI_DOCS_LOCAL_SITE=false
```

## Запуск CLI

### Генерация README

```bash
ai-docs --source ./my-project --readme --language ru
```

### Генерация MkDocs-сайта

```bash
ai-docs --source https://github.com/user/repo.git --mkdocs --language ru
```

### Принудительная перегенерация разделов

```bash
ai-docs --source . --mkdocs --regen architecture,configs --force
```

### Запуск без кэширования

```bash
ai-docs --source . --readme --no-cache
```

## Режимы работы

| Флаг | Описание |
|------|--------|
| `--readme` | Генерирует `README.md` в корне проекта |
| `--mkdocs` | Генерирует полный сайт документации |
| `--local-site` | Настраивает `mkdocs.yml` для локального хостинга (без публикации) |
| `--force` | Перезаписывает существующие файлы |
| `--regen [секции]` | Перегенерирует указанные разделы (через запятую) |
| `--no-cache` | Отключает кэширование LLM-ответов |

## Структура выходных файлов

После запуска создаются:

```
project-root/
├── README.md                     # краткая документация
├── .ai-docs/                     # полная документация в Markdown
│   ├── overview.md
│   ├── architecture.md
│   ├── modules/                  # описание модулей
│   ├── configs/                  # описание конфигов
│   └── _index.json               # навигационный индекс
├── mkdocs.yml                    # конфигурация сайта
├── ai_docs_site/                 # собранный сайт (при --mkdocs)
└── .ai_docs_cache/               # кэш LLM-запросов
```

## Интеграция в CI/CD

Пример для GitHub Actions:

```yaml
- name: Generate Docs
  run: |
    pip install ai-docs-gen
    ai-docs --source . --mkdocs --language ru
    mkdocs build -f mkdocs.yml
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Отладка и мониторинг

- Прогресс обработки логируется каждые 5 файлов.
- Ошибки накапливаются и выводятся в конце.
- Изменения фиксируются в `.ai-docs/changes.md`.
- Кэширование ускоряет повторные запуски: неизменённые файлы не обрабатываются повторно.

## Ограничения

- Максимальный размер файла: 200 КБ (настраивается через `--max-size`).
- Бинарные файлы и файлы в `.gitignore`, `.build_ignore`, `node_modules`, `.venv` и др. игнорируются.
- Для больших репозиториев рекомендуется увеличить `AI_DOCS_THREADS` и использовать `--regen` для частичной перегенерации.
