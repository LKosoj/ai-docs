# Запуск и окружение

## Базовый запуск

Инструмент запускается через CLI команду `ai-docs`. Минимальный вызов:

```bash
ai-docs --source /путь/к/проекту
```

Поддерживается анализ:
- Локальных директорий
- Локальных Git-репозиториев
- Удалённых репозиториев по URL (автоматическое клонирование)

Пример с URL:
```bash
ai-docs --source https://github.com/user/repo.git
```

## Переменные окружения

| Переменная | Назначение | Значение по умолчанию |
|-----------|------------|----------------------|
| `OPENAI_API_KEY` | Ключ API для доступа к LLM | Обязательна |
| `OPENAI_BASE_URL` | Базовый URL провайдера (для сторонних хостов) | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Модель для генерации | `gpt-4o-mini` |
| `OPENAI_MAX_TOKENS` | Макс. токенов в ответе | `1200` |
| `OPENAI_CONTEXT_TOKENS` | Лимит контекста модели | `8192` |
| `OPENAI_TEMPERATURE` | Уровень креативности генерации | `0.2` |
| `AI_DOCS_THREADS` | Количество параллельных потоков | `4` |
| `AI_DOCS_LOCAL_SITE` | Режим локального сайта MkDocs | `false` |
| `AI_DOCS_REGEN` | Секции для принудительной перегенерации | — |

## Основные CLI-параметры

```bash
ai-docs \
  --source <путь_или_url> \
  --output <директория_вывода> \
  --language ru \
  --threads 8 \
  --max-size 500000 \
  --include "*.py" "*.tf" \
  --exclude ".venv" "tests/*" \
  --readme \
  --mkdocs \
  --local-site \
  --regen configs,modules \
  --force \
  --no-cache
```

### Ключевые опции:
- `--source` — обязательный путь или URL
- `--output` — директория вывода (по умолчанию: корень проекта)
- `--language` — язык документации (`ru` или `en`)
- `--threads` — число потоков (переопределяет `AI_DOCS_THREADS`)
- `--max-size` — макс. размер файла в байтах (по умолчанию 200 КБ)
- `--include`/`--exclude` — фильтрация по путям и шаблонам
- `--readme`, `--mkdocs` — тип генерации
- `--local-site` — адаптация `mkdocs.yml` для локального запуска
- `--regen` — принудительная перегенерация разделов
- `--force` — перезапись существующего `README.md`
- `--no-cache` — отключение кэширования LLM-ответов
- `--cache-dir` — кастомная директория кэша (по умолчанию `.ai_docs_cache`)

## Режимы работы

### 1. Только README
```bash
ai-docs --source . --readme --force
```

### 2. Полный сайт MkDocs
```bash
ai-docs --source . --mkdocs --local-site
```
Создаёт `mkdocs.yml` и собирает сайт в `ai_docs_site/`.

### 3. Инкрементальная генерация
По умолчанию:
- Обновляются только изменённые файлы
- Не перезаписываются существующие `.md` в `.ai-docs/`
- Используется кэш в `.ai_docs_cache/`

Принудительная перегенерация:
```bash
ai-docs --source . --regen all
```

## Структура выходных артефактов

```
.
├── README.md                     # Краткое описание проекта
├── mkdocs.yml                    # Конфигурация сайта
├── ai_docs_site/                 # Собранный сайт (при --mkdocs)
├── .ai-docs/                     # Детальная документация
│   ├── index.md
│   ├── architecture.md
│   ├── modules/                  # Документация модулей
│   ├── configs/                  # Документация конфигов
│   ├── changes.md                # Отчёт об изменениях
│   └── _index.json               # Навигационный индекс
└── .ai_docs_cache/               # Кэш (при --no-cache не создаётся)
    ├── index.json
    ├── llm_cache.json
    └── intermediate/
```

## Запуск в CI/CD (пример для GitHub Actions)

```yaml
- name: Generate Docs
  run: |
    pip install ai-docs-gen
    ai-docs \
      --source . \
      --mkdocs \
      --local-site \
      --language en \
      --threads 4
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

> **Важно**: Убедитесь, что `OPENAI_API_KEY` задан. Без него запуск невозможен.
