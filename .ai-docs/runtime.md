# Запуск и окружение

```markdown
# Запуск и окружение

## Базовые требования
- Python 3.9+
- Доступ к LLM через API (например, OpenAI, Azure OpenAI)
- Установленный пакет `ai_docs` (через `pip install ai_docs` или локально)

## Настройка окружения
Перед запуском задайте обязательные переменные в файле `.env` или через системные переменные:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # опционально, для кастомных эндпоинтов
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.2
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192

AI_DOCS_THREADS=4
AI_DOCS_LOCAL_SITE=false
```

> **Важно**: `OPENAI_API_KEY` обязателен. Для локального запуска сайта документации установите `AI_DOCS_LOCAL_SITE=true`.

## Запуск CLI
Основная команда:

```bash
ai_docs --source <путь_или_url> [опции]
```

### Примеры запуска

**1. Генерация README для локального проекта:**
```bash
ai_docs --source . --readme --language ru --force
```

**2. Сборка MkDocs-сайта из удалённого репозитория:**
```bash
ai_docs --source https://github.com/user/repo.git --mkdocs --local-site
```

**3. Генерация на английском с кастомными потоками:**
```bash
ai_docs --source . --mkdocs --language en --threads 6
```

## Режимы работы
| Флаг | Назначение |
|------|----------|
| `--readme` | Генерирует `README.md` в корне проекта |
| `--mkdocs` | Создаёт `mkdocs.yml` и структуру `.ai-docs/` для сборки сайта |
| `--local-site` | Настраивает `mkdocs.yml` для локального просмотра (без `site_url`, `use_directory_urls: false`) |

## Каталоги и артефакты
После запуска создаются:
- `.ai-docs/` — сгенерированные страницы документации
- `ai_docs_site/` — собранный статический сайт (при `--mkdocs`)
- `.ai_docs_cache/` — кэш LLM и хэшей файлов (можно очистить вручную)
- `README.md` — перезаписывается только с флагом `--force`

## Особенности запуска
- Удалённые репозитории клонируются с `--depth 1` для скорости.
- Файлы игнорируются согласно `.gitignore`, `.build_ignore` и встроенным правилам (например, `node_modules`, `.venv`).
- Бинарные файлы и символические ссылки пропускаются.
- Временные директории при ошибках удаляются автоматически.

## Диагностика
При проблемах проверьте:
1. Наличие `OPENAI_API_KEY`
2. Доступность API (таймауты: 30с подключение, 120с ответ)
3. Размер файлов (макс. 200 КБ по умолчанию)
4. Логи ошибок в stdout/stderr

Для отладки кэширования используйте `--cache-dir .ai_docs_cache` и проверьте содержимое `llm_cache.json`.
```
