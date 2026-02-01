# Запуск и окружение

## Установка

Установите пакет через `pip`:

```bash
pip install ai-docs-gen
```

Или в режиме разработки из корня проекта:

```bash
pip install -e .
```

## Переменные окружения

Инструмент использует следующие переменные окружения. Рекомендуется задавать их в файле `.env` в корне проекта.

| Переменная               | Назначение                                      | По умолчанию                     |
|--------------------------|-------------------------------------------------|----------------------------------|
| `OPENAI_API_KEY`         | Ключ для доступа к OpenAI или совместимому API  | Обязательна                      |
| `OPENAI_BASE_URL`        | Базовый URL API (для локальных LLM)             | `https://api.openai.com/v1`      |
| `OPENAI_MODEL`           | Модель LLM для генерации                        | `gpt-4o-mini`                    |
| `OPENAI_TEMPERATURE`     | Температура генерации (0.0 — строго, 1.0 — креативно) | `0.2`                        |
| `OPENAI_MAX_TOKENS`      | Максимальное число токенов в ответе             | `1200`                           |
| `OPENAI_CONTEXT_TOKENS`  | Общий лимит контекста модели                    | `8192`                           |
| `AI_DOCS_THREADS`        | Количество потоков для параллельной обработки   | Автоопределение (CPU-cores)      |
| `AI_DOCS_LOCAL_SITE`     | Режим локального сайта (без публикации)         | `false`                          |

Пример `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
AI_DOCS_THREADS=4
AI_DOCS_LOCAL_SITE=true
```

## Запуск CLI

### Базовый запуск (локальная директория)

```bash
ai-docs --source .
```

Сгенерирует `README.md` и сайт MkDocs в `ai_docs_site/`.

### Указание источника

Поддерживается:
- Локальная директория: `--source ./my-project`
- Git-репозиторий: `--source https://github.com/user/repo.git`

```bash
ai-docs --source https://github.com/example/project.git
```

### Выбор формата вывода

```bash
# Только README
ai-docs --source . --readme

# Только MkDocs
ai-docs --source . --mkdocs

# Оба (по умолчанию)
ai-docs --source .
```

### Язык документации

```bash
ai-docs --source . --language ru  # или en
```

По умолчанию: `ru`.

### Управление производительностью

```bash
ai-docs --source . --threads 8
```

Или через переменную окружения: `AI_DOCS_THREADS=8`.

### Кэширование

По умолчанию включено. Для отключения:

```bash
ai-docs --source . --no-cache
```

Кэш хранится в `.ai_docs_cache/`. Промежуточные данные — в `.ai-docs/`.

### Принудительная перезапись

```bash
ai-docs --source . --force
```

Перезапишет существующий `README.md`.

### Фильтрация файлов

```bash
ai-docs --source . --include "*.py" --include "Dockerfile" --exclude "*.test.py"
```

Используются glob-шаблоны. Также учитывается `.gitignore` и `.build_ignore`.

### Ограничение размера файлов

```bash
ai-docs --source . --max-size 500000  # 500 КБ
```

Файлы больше игнорируются.

## Режимы работы

### Локальный сайт (без публикации)

```bash
ai-docs --source . --local-site
```

Или через переменную: `AI_DOCS_LOCAL_SITE=true`.  
Настройки MkDocs адаптируются под локальный запуск.

### Отладка

Для запуска без установки пакета:

```bash
python -m ai_docs --source . --readme --language ru
```

## Структура выходных данных

После выполнения создаются:

```
.ai-docs/           # Промежуточные данные, навигация, changes.md
.ai_docs_cache/     # Кэш LLM и хэши файлов
README.md           # Краткая документация (если --readme)
mkdocs.yml          # Конфиг сайта
ai_docs_site/       # Сборка сайта (если --mkdocs)
```

## Требования

- Python 3.8+
- `git` (для обработки удалённых репозиториев)
- Доступ к OpenAI-совместимому API

## Пример полного запуска

```bash
AI_DOCS_THREADS=6 AI_DOCS_LOCAL_SITE=true \
ai-docs \
  --source . \
  --readme \
  --mkdocs \
  --language ru \
  --include "*.py" \
  --include "Dockerfile" \
  --max-size 300000 \
  --force
```
