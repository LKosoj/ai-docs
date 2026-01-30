# ai_docs — генератор технической документации

## Обзор
`ai_docs` — CLI‑инструмент для генерации технической документации по коду и конфигурациям.
Поддерживает локальные папки, локальные git‑проекты и удалённые git‑репозитории.
Генерирует `README.md` и MkDocs‑сайт (с автоматической сборкой).

Ключевые возможности:
- Автоопределение доменов инфраструктуры (Kubernetes, Helm, Terraform, Ansible, Docker, CI/CD)
- Инкрементальная генерация и кэширование
- Учет `.gitignore` и фильтрация файлов
- Параллельная LLM‑суммаризация (`--threads` / `AI_DOCS_THREADS`)
- Отчёт об изменениях в `docs/changes.md`

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
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192
OPENAI_TEMPERATURE=0.2
AI_DOCS_THREADS=1
AI_DOCS_LOCAL_SITE=false
```

3) Генерация README и MkDocs:
```bash
python -m ai_docs --source .
```

Альтернативно:
```bash
python ai_docs --source .
```

## Примеры использования

Локальная папка:
```bash
python -m ai_docs --source /path/to/project
```

Локальный git‑проект:
```bash
python -m ai_docs --source ~/projects/my-repo
```

Удалённый репозиторий:
```bash
python -m ai_docs --source https://github.com/org/repo.git
```

Только README:
```bash
python -m ai_docs --source . --readme
```

Только MkDocs:
```bash
python -m ai_docs --source . --mkdocs
```

Локальный режим для MkDocs:
```bash
python -m ai_docs --source . --mkdocs --local-site
```

## Что генерируется
- `README.md` — краткое описание проекта
- `docs/` — страницы документации
- `docs/changes.md` — изменения с последней генерации
- `mkdocs.yml` — конфиг MkDocs
- `ai_docs_site/` — собранный сайт MkDocs
- `.ai_docs_cache/` — кэш и промежуточные summary‑файлы

## CLI‑параметры
- `--source <path|url>` — источник
- `--output <path>` — выходная директория (по умолчанию: source для локальных путей, `./output/<repo>` для URL)
- `--readme` — генерировать только README
- `--mkdocs` — генерировать только MkDocs
- `--language ru|en` — язык документации
- `--include/--exclude` — фильтры
- `--max-size` — максимальный размер файла
- `--threads` — число потоков LLM
- `--cache-dir` — директория кэша (по умолчанию `.ai_docs_cache`)
- `--no-cache` — отключить LLM‑кэш
- `--local-site` — добавить `site_url` и `use_directory_urls` в `mkdocs.yml`

Поведение по умолчанию: если не указаны `--readme` и `--mkdocs`, генерируются оба артефакта.

## MkDocs
Сборка выполняется автоматически в конце генерации:
```
mkdocs build -f mkdocs.yml
```

## Исключения
Сканер учитывает `.gitignore` и дефолтные исключения:
`.venv`, `node_modules`, `ai_docs_site`, `.ai_docs_cache`, `dist`, `build`, т.д.

## Разработка и вклад
- Установите зависимости (см. «Быстрый старт»)
- Запускайте через `python -m ai_docs ...` для отладки
- PR и предложения приветствуются

## Лицензия
MIT
