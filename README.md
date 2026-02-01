# ai_docs — генератор технической документации

[English version](README_EN.md) | [Русская версия](README.md)

## Обзор
`ai_docs` — CLI‑инструмент для генерации технической документации по коду и конфигурациям.
Поддерживает локальные папки, локальные git‑проекты и удалённые git‑репозитории.
Генерирует `README.md` и MkDocs‑сайт (с автоматической сборкой).

Ключевые возможности:
- Автоопределение доменов инфраструктуры (Kubernetes, Helm, Terraform, Ansible, Docker, CI/CD, Observability, Service Mesh / Ingress, Data / Storage)
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

Альтернатива (установка как пакет):
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install ai-docs-gen
```

Локальная установка в editable‑режиме:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

2) Настройка переменных окружения (пример — `.env.example`):
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

Если инструмент установлен как пакет, можно задать переменные окружения так:
```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_MAX_TOKENS="1200"
export OPENAI_CONTEXT_TOKENS="8192"
export OPENAI_TEMPERATURE="0.2"
export AI_DOCS_THREADS="1"
export AI_DOCS_LOCAL_SITE="false"
```

3) Генерация README и MkDocs:
```bash
python -m ai_docs --source .
```

Альтернативно:
```bash
python ai_docs --source .
```

Если установлен как пакет:
```bash
ai-docs --source .
```

Примечание для Windows:
- Пути обрабатываются корректно, но внутри всегда нормализуются в формат с `/`.
- Если используете PowerShell, пример активации venv и переменных окружения:
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
$env:OPENAI_API_KEY="your_api_key_here"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_MODEL="gpt-4o-mini"
$env:OPENAI_MAX_TOKENS="1200"
$env:OPENAI_CONTEXT_TOKENS="8192"
$env:OPENAI_TEMPERATURE="0.2"
$env:AI_DOCS_THREADS="1"
$env:AI_DOCS_LOCAL_SITE="false"
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
- `.ai-docs/` — страницы документации
- `.ai-docs/changes.md` — изменения с последней генерации
- `.ai-docs/modules/` — детальная документация модулей (страница на модуль, Doxygen‑подобное описание функций/классов/параметров)
- `.ai-docs/configs/` — документация конфигов проекта (обзор + страницы конфигов в универсальном стиле)
- `.ai-docs/_index.json` — навигационный индекс документации (правила маршрутизации, список секций и модулей)
- `mkdocs.yml` — конфиг MkDocs
- `ai_docs_site/` — собранный сайт MkDocs
- `.ai_docs_cache/` — кэш и промежуточные summary‑файлы

## Поддерживаемые языки и расширения
Поддержка основана на расширениях кода в `ai_docs/domain.py`:
`.py`, `.pyi`, `.pyx`, `.js`, `.jsx`, `.ts`, `.tsx`, `.go`, `.java`, `.c`, `.cc`, `.cpp`, `.h`, `.hpp`, `.rs`, `.rb`, `.php`, `.cs`, `.kt`, `.kts`, `.swift`, `.m`, `.mm`, `.vb`, `.bas`, `.sql`, `.pas`, `.dpr`, `.pp`, `.r`, `.pl`, `.pm`, `.f`, `.for`, `.f90`, `.f95`, `.f03`, `.f08`, `.sb3`, `.adb`, `.ads`, `.asm`, `.s`, `.ino`, `.htm`, `.html`, `.css`.

## Индекс документации
Файл `.ai-docs/_index.json` строится автоматически при генерации и содержит:
- список секций и модулей (пути и краткие описания);
- правила маршрутизации: приоритет `modules/index.md → modules/* → index.md/architecture.md/conventions.md`;
- принцип ранжирования: частота ключевых совпадений + приоритет файла.

## .ai-docs.yaml (расширения)
Если в проекте есть файл `.ai-docs.yaml`, он задаёт приоритетный список расширений для сканирования.
Если файла нет, он создаётся автоматически на основе текущих `*_EXTENSIONS`.

Формат (поддерживаются map и list для расширений):
```yaml
code_extensions:
  .py: Python
  .ts: TypeScript
doc_extensions:
  .md: Markdown
  .rst: reStructuredText
config_extensions:
  .yml: YAML
  .json: JSON
exclude:
  - "temp/*"
  - "*.log"
```

## CLI‑параметры
- `--source <path|url>` — источник
- `--output <path>` — выходная директория (по умолчанию: source для локальных путей, `./output/<repo>` для URL)

## Тестирование
Тесты находятся в каталоге `tests/`:
- `test_cache.py`
- `test_changes.py`
- `test_scanner.py`

Запуск (из корня проекта):
```bash
python -m pytest
```
- `--readme` — генерировать только README
- `--mkdocs` — генерировать только MkDocs
- `--language ru|en` — язык документации
- `--include/--exclude` — фильтры
- `--max-size` — максимальный размер файла
- `--threads` — число потоков LLM
- `--cache-dir` — директория кэша (по умолчанию `.ai_docs_cache`)
- `--no-cache` — отключить LLM‑кэш
- `--local-site` — добавить `site_url` и `use_directory_urls` в `mkdocs.yml`
- `--force` — перезаписать `README.md`, если он уже существует

Поведение по умолчанию: если не указаны `--readme` и `--mkdocs`, генерируются оба артефакта.

## MkDocs
Сборка выполняется автоматически в конце генерации:
```
mkdocs build -f mkdocs.yml
```

## Исключения
Сканер учитывает `.gitignore`, `.build_ignore` и дефолтные исключения:
`.venv`, `node_modules`, `ai_docs_site`, `.ai-docs`, `.ai_docs_cache`, `dist`, `build`, т.д.

## Разработка и вклад
- Установите зависимости (см. «Быстрый старт»)
- Запускайте через `python -m ai_docs ...` для отладки
- PR и предложения приветствуются

## Лицензия
MIT
