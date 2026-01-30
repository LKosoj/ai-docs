# ai_docs — Генератор технической документации

## Обзор
`ai_docs` — CLI‑инструмент для генерации технической документации по коду и конфигурациям.
Поддерживает локальные папки, локальные git‑проекты и удалённые git‑репозитории.
Генерирует `README.md` и MkDocs‑сайт (с автосборкой).

Ключевые возможности:
- Автоопределение доменов инфраструктуры (Kubernetes, Helm, Terraform, Ansible, Docker, CI)
- Инкрементальная генерация и кэширование
- Учет `.gitignore`, фильтрация по типу и размеру файлов
- Параллельная LLM‑суммаризация (`--threads` / `AI_DOCS_THREADS`)
- Отчёт об изменениях `docs/changes.md`

## Быстрый старт

1) Установка зависимостей:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2) Настройка `.env` (пример — `.env.example`):
```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_CONTEXT_TOKENS=8192
OPENAI_TEMPERATURE=0.2
AI_DOCS_THREADS=1
AI_DOCS_LOCAL_SITE=false
```

3) Запуск генерации:
```bash
ai-docs --source . --readme --mkdocs
```

Альтернативно:
```bash
python -m ai_docs --source . --readme --mkdocs
python ai_docs --source . --readme --mkdocs
```

## Что генерируется
- `README.md` — краткое описание проекта
- `docs/` — страницы документации
- `mkdocs.yml` — конфиг MkDocs
- `ai_docs_site/` — собранный сайт MkDocs
- `.ai_docs_cache/` — кэш и промежуточные summary‑файлы

## MkDocs
Сборка выполняется автоматически в конце генерации:
```
mkdocs build -f mkdocs.yml
```

Если нужен локальный режим (для корректных ссылок в файловой системе):
```bash
ai-docs --source . --readme --mkdocs --local-site
```

## CLI‑параметры
- `--source <path|url>` — источник
- `--readme` — генерировать README
- `--mkdocs` — генерировать MkDocs
- `--language ru|en`
- `--include/--exclude` — фильтры
- `--max-size` — максимальный размер файла
- `--threads` — число потоков LLM
- `--local-site` — добавить `site_url` и `use_directory_urls` в `mkdocs.yml`
- `--no-cache` — отключить LLM‑кэш

## Кэш и инкрементальная генерация
Кэш хранится в `.ai_docs_cache/` внутри проекта. При повторном запуске:
- пересчитываются только изменённые/добавленные файлы,
- удалённые файлы удаляются из кэша,
- “сиротские” страницы документации удаляются автоматически.

## Исключения
Сканер учитывает `.gitignore` и дефолтные исключения:
`.venv`, `node_modules`, `ai_docs_site`, `.ai_docs_cache`, `site`, `dist`, `build`, т.д.

## Лицензия
MIT
