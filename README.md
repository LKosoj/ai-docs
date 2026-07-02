# ai_docs — генератор технической документации

[English version](README_EN.md) | [Русская версия](README.md)

## Обзор
`ai_docs` — CLI‑инструмент для генерации технической документации по коду и конфигурациям.
Поддерживает локальные папки, локальные git‑проекты и удалённые git‑репозитории.
Генерирует `README.md` и MkDocs‑сайт (с автоматической сборкой).

Ключевые возможности:
- Автоопределение доменов инфраструктуры (Kubernetes, Helm, Terraform, Ansible, Docker, CI/CD, Observability, Service Mesh / Ingress, Data / Storage)
- Инкрементальная генерация и кэширование
- Учет `.gitignore` и фильтрация файлов без записи служебных файлов во время сканирования
- Параллельное сканирование и LLM‑суммаризация с глобальным лимитом одновременных запросов к LLM (`--threads` / `AI_DOCS_THREADS`)
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

Для команды `watch` установите optional extra:
```bash
pip install -e ".[watch]"
```

2) Настройка переменных окружения (пример — `.env.example`):
```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=1200
OPENAI_CONTEXT_TOKENS=8192
OPENAI_TEMPERATURE=0.2
AI_DOCS_THREADS=5
AI_DOCS_LOCAL_SITE=false
AI_DOCS_INSECURE_SSL=false
```

Если инструмент установлен как пакет, можно задать переменные окружения так:
```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_BASE_URL=""
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_MAX_TOKENS="1200"
export OPENAI_CONTEXT_TOKENS="8192"
export OPENAI_TEMPERATURE="0.2"
export AI_DOCS_THREADS="5"
export AI_DOCS_LOCAL_SITE="false"
export AI_DOCS_INSECURE_SSL="false"
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
$env:OPENAI_BASE_URL=""
$env:OPENAI_MODEL="gpt-4o-mini"
$env:OPENAI_MAX_TOKENS="1200"
$env:OPENAI_CONTEXT_TOKENS="8192"
$env:OPENAI_TEMPERATURE="0.2"
$env:AI_DOCS_THREADS="5"
$env:AI_DOCS_LOCAL_SITE="false"
$env:AI_DOCS_INSECURE_SSL="false"
```

## Подкоманды CLI

`ai-docs` предоставляет несколько подкоманд:

| Команда | Назначение |
| --- | --- |
| `gen` | Сгенерировать/обновить документацию (поведение по умолчанию) |
| `lint` | Проверить, есть ли файлы с изменениями без обновления документации. Завершается с ненулевым кодом, если есть stale‑файлы |
| `watch` | Следить за изменениями в исходниках и автоматически регенерировать документацию (требует пакет `watchdog`) |
| `pr-diff` | Регенерировать документацию только для файлов, изменённых относительно базовой ветки (`--base`) |

Примеры:
```bash
ai-docs gen --source . --mkdocs
ai-docs lint --source .
ai-docs watch --source . --mkdocs --debounce 3.0
ai-docs pr-diff --source . --base main
```

Вызов `ai-docs --source .` (без явной подкоманды) сохраняет обратную совместимость и эквивалентен `ai-docs gen --source .`.

## Примеры использования

Локальная папка:
```bash
python -m ai_docs /path/to/project
```

или явно:
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

## Интеграция в CI/CD

Готовые шаблоны пайплайнов лежат в `examples/ci/`:
- `examples/ci/github-actions.yml` — GitHub Actions: `lint` на PR, `gen` на push в `main`, автокоммит обновлённой документации.
- `examples/ci/gitlab-ci.yml` — GitLab CI: отдельные stages `lint` и `docs`.

Минимальный пример для GitHub Actions:
```yaml
- name: Generate Docs
  run: |
    pip install ai-docs-gen
    ai-docs gen --source . --mkdocs --readme --language en --force
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Pre-commit hook

В репозитории есть `.pre-commit-hooks.yaml` с двумя хуками:
- `ai-docs-lint` — запускается на `pre-commit` и падает, если документация устарела.
- `ai-docs-regen` — запускается на `pre-push` и перегенерирует документацию.

Подключение в чужом проекте:
```yaml
repos:
  - repo: https://github.com/<your>/ai-docs
    rev: main
    hooks:
      - id: ai-docs-lint
      - id: ai-docs-regen
```

## Что генерируется
- `README.md` — краткое описание проекта
- `.ai-docs/` — страницы документации
- `.ai-docs/overview.md` — сохранённый обзор проекта (используется для README и MkDocs)
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
Если файла нет, используются встроенные правила из `ai_docs/domain_rules.py`; сканирование не создаёт `.ai-docs.yaml` автоматически.

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

# Базовый URL для ссылок на исходники в сгенерированных страницах модулей/конфигов.
# Если задан, в начале каждой страницы модуля появится строка вида
# *Источник:* [`path/to/file.py`](<source_url>/path/to/file.py)
source_url: https://github.com/your-org/your-repo/blob/main

# Пользовательские промпты. Переопределяют встроенные шаблоны; неуказанные
# ключи берутся из значений по умолчанию. Доступные ключи:
#   summary, summary_combine,
#   module_summary, module_summary_reformat,
#   config_summary, config_summary_reformat
prompts:
  summary: |
    Ты эксперт по технической документации. Сформируй краткое описание файла
    в нашем корпоративном стиле. Одно‑два предложения, без заголовков и списков.
```

## CLI‑параметры
- `--source <path|url>` — источник
- `--output <path>` — выходная директория (по умолчанию: source для локальных путей, `./output/<repo>` для URL)

## Тестирование
Тесты находятся в каталоге `tests/`:
- `test_cache.py`
- `test_changes.py`
- `test_cli.py`
- `test_config.py`
- `test_generated_docs.py`
- `test_generator.py`
- `test_generator_shared.py`
- `test_llm.py`
- `test_packaging.py`
- `test_performance.py`
- `test_prompts.py`
- `test_scanner.py`
- `test_site_config.py`
- `test_summary.py`
- `test_watch.py`

Запуск (из корня проекта):
```bash
python -m pytest
```
- `--readme` — генерировать только README
- `--mkdocs` — генерировать только MkDocs
- `--language ru|en` — язык документации
- `--include/--exclude` — фильтры
- `--max-size` — максимальный размер файла
- `--threads` — число параллельных воркеров для сканирования и глобальный лимит одновременных запросов к LLM (см. раздел «Параллельность»)
- `--cache-dir` — директория кэша (по умолчанию `.ai_docs_cache`)
- `--no-cache` — отключить LLM‑кэш
- `--local-site` — добавить `site_url` и `use_directory_urls` в `mkdocs.yml`
- `--force` — перезаписать `README.md`, если он уже существует
- `--regen` — перечень разделов для принудительной перегенерации (через запятую, например `architecture,configs,changes`, либо `all`)

Поведение по умолчанию: если не указаны `--readme` и `--mkdocs`, генерируются оба артефакта.
Разделы в `.ai-docs/*.md` (включая `overview.md`) не перегенерируются, если файл уже существует, кроме указанных в `--regen`.
Если количество модулей меньше порога `AI_DOCS_REGEN_ALL_THRESHOLD` (по умолчанию 50), все разделы перегенерируются автоматически (в том числе `overview.md`).
При запуске без параметров для разделов выводится подсказка с примером `--regen`.
Если модулей больше 100, `modules/index.md` автоматически разбивается на страницы по 100 элементов с навигацией «←/→».
Если конфигов больше 100, `configs/index.md` также разбивается на страницы по 100 элементов с навигацией «←/→».

Ошибки конфигурации, повреждённого кэша и LLM‑суммаризации завершают команду ненулевым кодом. При ошибках суммаризации финальные артефакты не перезаписываются как успешный результат.

`pr-diff` выполняет полный scan текущего дерева, но повторно суммаризирует только файлы из `git diff --name-status <base>...HEAD`; неизменённые файлы не считаются удалёнными из-за частичного diff.

## Python API

Для embedded‑сценариев доступен публичный async API:
```python
from ai_docs.generation_config import GenerationConfig
from ai_docs.generator import generate_docs_async

await generate_docs_async(..., generation_config=GenerationConfig(source_url="https://example.com/repo/"))
```

Синхронный `generate_docs(...)` остаётся тонкой обёрткой для CLI и обычных скриптов.

## TLS

Проверка TLS включена по умолчанию для всех запросов к OpenAI‑совместимому endpoint. Для self-signed окружений можно явно отключить проверку:
```bash
AI_DOCS_INSECURE_SSL=true
```
При таком запуске CLI печатает предупреждение.

## Параллельность и лимит LLM‑запросов

Параметр `--threads N` (или переменная окружения `AI_DOCS_THREADS=N`, по умолчанию `5`)
задаёт **глобальный верхний предел числа одновременных запросов к LLM** по всему пайплайну.
Лимит реализован как общий `asyncio.Semaphore` в `LLMClient` и гарантированно действует на:

- чанки одного файла при суммаризации (`_summarize_chunks`);
- одновременные суммаризации разных файлов;
- параллельную подготовку контекстов (`overview`, `architecture`, `runtime`, `conventions`,
  доменные контексты Kubernetes/Helm/…, `index`, `modules`, `changes`);
- параллельную генерацию финальных разделов и README.

Cache‑hit'ы слоты семафора **не занимают** — параллельные повторные запросы с тем же payload
отдаются из кэша, не дожидаясь свободного слота.

Тот же `--threads` используется и для пула потоков при сканировании файлов.

Рекомендации по подбору значения:
- При ошибках `429 Too Many Requests` от провайдера понизьте до `2`–`3`.
- На мощном платном endpoint без жёсткого rate‑limit имеет смысл поднять до `10`–`20`.
- `--threads 1` сериализует все LLM‑вызовы (удобно для отладки и детерминированных прогонов).

При запуске в логе выводится строка вида:
```
[ai-docs] llm: model=gpt-4o-mini context=8192 max_tokens=1200 concurrency=5
```
где `concurrency` — фактически применяемый глобальный лимит.

## MkDocs
Сборка выполняется автоматически в конце генерации:
```
mkdocs build -f mkdocs.yml
```

## Исключения
Сканер учитывает `.gitignore`, `.build_ignore` и дефолтные исключения:
`.venv`, `node_modules`, `ai_docs_site`, `.ai-docs`, `.ai_docs_cache`, `dist`, `build`, т.д.
GitHub Actions workflow-файлы в `.github/workflows/*.yml` и `.github/workflows/*.yaml` включаются в scan и классифицируются как CI.

## Разработка и вклад
- Установите зависимости (см. «Быстрый старт»)
- Запускайте через `python -m ai_docs ...` для отладки
- PR и предложения приветствуются

## Лицензия
MIT
