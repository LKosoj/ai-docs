# Запуск и окружение

```markdown
# Запуск и окружение

## Установка и запуск

Инструмент `ai_docs` доступен как CLI-утилита. Для запуска:

1. Установите пакет:
   ```bash
   pip install ai_docs
   ```

2. Запустите генерацию документации:
   ```bash
   ai_docs --source ./my-project --language ru --readme --mkdocs
   ```

Поддерживается запуск как модуля:
```bash
python -m ai_docs --source https://github.com/user/repo.git
```

## Источники данных

Поддерживаются три типа источников:
- **Локальная директория**: `--source ./project`
- **Удалённый Git-репозиторий**: `--source https://github.com/user/repo.git`
- **Локальный репозиторий**: `--source /path/to/repo/.git`

При работе с URL репозиторий клонируется в временный каталог (`--depth 1`) и удаляется после завершения.

## Обязательные настройки

- `--source` — путь или URL к проекту (обязательный).
- `--language` — язык документации: `ru` или `en` (по умолчанию `ru`).

## Опциональные параметры

| Параметр | Назначение | По умолчанию |
|--------|-----------|-------------|
| `--output` | Директория вывода | `./` или `output/<repo>` |
| `--readme` | Генерировать `README.md` | включено |
| `--mkdocs` | Генерировать `mkdocs.yml` и `docs/` | включено |
| `--local-site` | Настроить MkDocs для локального просмотра | отключено |
| `--no-cache` | Отключить кэширование LLM-ответов | включено |
| `--threads` | Количество потоков обработки | значение `AI_DOCS_THREADS` |
| `--include` | Glob-паттерны для включения файлов | стандартные расширения |
| `--exclude` | Glob-паттерны для исключения | `.venv`, `node_modules`, `build`, `dist` |
| `--max-size` | Макс. размер файла (байт) | 204800 (200 КБ) |
| `--cache-dir` | Директория кэша | `.ai_docs_cache` |

Пример фильтрации:
```bash
--include "*.py" --include "docs/*.md" --exclude "*.test.*"
```

## Переменные окружения

| Переменная | Назначение | Пример |
|-----------|-----------|--------|
| `OPENAI_API_KEY` | Ключ доступа к LLM | `sk-...` |
| `OPENAI_BASE_URL` | Базовый URL API | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Модель для генерации | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Температура генерации | `0.2` |
| `OPENAI_MAX_TOKENS` | Макс. токенов в ответе | `1200` |
| `OPENAI_CONTEXT_TOKENS` | Лимит контекста | `8192` |
| `AI_DOCS_THREADS` | Количество потоков | `4` |
| `AI_DOCS_LOCAL_SITE` | Локальный режим MkDocs | `true` |

Файл `.env` в корне проекта загружается автоматически.

## Режимы работы

### 1. Генерация README
Создаёт краткое описание проекта в `README.md`:
```bash
ai_docs --source . --readme --no-mkdocs
```

### 2. Генерация сайта документации
Создаёт `mkdocs.yml`, `docs/` и собирает сайт:
```bash
ai_docs --source . --mkdocs --local-site
```
После генерации сайт можно запустить:
```bash
cd ai_docs_site && python -m http.server 8000
```

### 3. Инкрементальная обработка
Кэширование в `.ai_docs_cache/` позволяет пересчитывать только изменённые файлы. Отчёт сохраняется в `docs/changes.md`.

Для полной перегенерации:
```bash
ai_docs --source . --no-cache
```

## Поддерживаемые технологии

Автоматически распознаются:
- **Kubernetes**: `deployment.yaml`, `kustomization.yml`, `apiVersion: apps/v1`
- **Helm**: `Chart.yaml`, `values.yaml`, `/templates/`
- **Terraform**: `.tf`, `.tfvars`
- **Ansible**: пути с `/roles/`, `/tasks/`
- **Docker**: `Dockerfile`, `docker-compose.yml`
- **CI/CD**: `.gitlab-ci.yml`, `Jenkinsfile`, `.github/workflows/`

Распознанные домены интегрируются в структуру документации (раздел "Конфиги" в `mkdocs.yml`).
```
