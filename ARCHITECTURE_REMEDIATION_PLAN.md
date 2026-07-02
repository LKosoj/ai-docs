# План доработки по ARCHITECTURE_AUDIT.md

Дата: 2026-07-02

## Цель

Закрыть все пункты из `ARCHITECTURE_AUDIT.md` без откладывания задач. Работы идут по приоритету P0 -> P1 -> P2 -> P3, но независимые группы выполняются параллельно там, где write-set не пересекается.

## Общие правила выполнения

- Каждое изменение поведения сопровождается тестом.
- После каждой волны: targeted tests для затронутой области.
- Перед финалом: `pytest -q` в `.venv`, `ruff check ai_docs tests`, code-review сабагент.
- Если ревью находит ошибки или предупреждения, исправить и повторить ревью до чистого результата.
- Не трогать чужое изменение версии в `pyproject.toml` без необходимости; если dependencies меняются, сохранить текущую версию `0.1.11`.
- Не добавлять молчаливые fallback-режимы. Legacy fallback допустим только явно и с логированием.

## Волна 0. Планирование и распределение

1. Зафиксировать общий план в этом файле.
   Проверка: файл существует и покрывает все пункты аудита.

2. Запустить сабагентов на детальную проработку независимых групп:
   - Агент A: CLI, `pr-diff`, scanner side effects.
   - Агент B: docs path/index/output.
   - Агент C: LLM/runtime/watch/errors.
   - Агент D: config/dependencies/testing/cache policy.

3. Согласовать результаты агентов с текущим планом.
   Проверка: нет конфликтующих write-set или неявных fallback.

## Волна 1. P0-критические корректности

### 1.1 Exit codes для `python -m ai_docs`

Проблема: `ai_docs/__main__.py` вызывает `main()` без `sys.exit`.

Файлы:
- `ai_docs/__main__.py`
- `tests/test_cli.py`

Работы:
- Завершать процесс через `sys.exit(main())`.
- Добавить subprocess-тест, который запускает `python -m ai_docs lint --source <tmpdir>` и ожидает `rc=2` при отсутствующем кэше.

Проверка:
- `pytest -q tests/test_cli.py::...`

### 1.2 Ошибки LLM-суммаризации не должны давать успешную генерацию

Проблема: `summarize_entries()` копит ошибки, а `generate_docs()` только печатает их.

Файлы:
- `ai_docs/generator.py`
- `ai_docs/generator_summarize.py`
- `tests/test_summary.py` или новый `tests/test_generator.py`

Работы:
- Ввести исключение уровня генерации, например `GenerationError`.
- После фаз summarization падать, если накоплены ошибки.
- Не запускать финальный write/build как успешный результат при ошибках.
- Тест: fake LLM падает на файле, `generate_docs`/async API возвращает исключение.

Проверка:
- targeted generator test.

### 1.3 Безопасный `pr-diff`

Проблема: partial scan превращает неотсканированные файлы в `deleted`.

Файлы:
- `ai_docs/cli_prdiff.py`
- `ai_docs/generator.py`
- `ai_docs/generator_cache.py`
- `tests/test_cli.py` или новый `tests/test_prdiff.py`

Работы:
- Делать полный scan для актуального `file_map`.
- Передавать changed paths в генератор как ограничение для summarization, не как ограничение всего snapshot.
- Учитывать deleted files из `git diff --name-status`, а не выводить deleted из partial snapshot.
- Тест: repo с двумя файлами, cache baseline на оба, изменен один; второй не попадает в deleted.

Проверка:
- targeted pr-diff tests.

## Волна 2. P1 consistency scanner/output/index

### 2.1 `.github/workflows` должен сканироваться как CI

Файлы:
- `ai_docs/scanner.py`
- `tests/test_scanner.py`

Работы:
- Убрать `.github` из безусловного pruning.
- Оставить excludes для тяжелых/служебных директорий.
- Добавить тест на `.github/workflows/build.yml`.

Проверка:
- `pytest -q tests/test_scanner.py`

### 2.2 `scan_source()` должен быть read-only

Файлы:
- `ai_docs/scanner.py`
- `ai_docs/cli.py` при необходимости для явного init/create config
- `tests/test_scanner.py`
- README при изменении пользовательского поведения

Работы:
- Убрать автосоздание `.ai-docs.yaml` из `_load_extension_config`.
- Если нужен генератор дефолтного конфига, вынести в отдельную функцию/команду или оставить только внутренний helper без автозапуска.
- Тест: scan директории без `.ai-docs.yaml` не создает файл.

Проверка:
- scanner tests.

### 2.3 Единые пути generated pages и корректный `_index.json`

Файлы:
- `ai_docs/generator_shared.py`
- `ai_docs/generator_sections.py`
- `ai_docs/generator_output.py`
- `ai_docs/mkdocs.py` при необходимости
- `tests/test_summary.py` или новый `tests/test_output_index.py`

Работы:
- Ввести helpers `module_doc_path(source_path)` и `config_doc_path(source_path)`.
- Использовать их в генерации страниц, nav и `_index.json`.
- Перестроить `_index.json` после cleanup или строить его из финального keep-set.
- Тест: generated module path в `_index.json` совпадает с фактическим `module_pages`.
- Тест: orphan после cleanup не остается в `_index.json`.

Проверка:
- targeted output/index tests.

## Волна 3. P1 runtime, async, LLM safety

### 3.1 Публичный async API генерации

Файлы:
- `ai_docs/generator.py`
- callers: `cli.py`, `cli_prdiff.py`, `cli_watch.py` при необходимости
- tests

Работы:
- Экспортировать `generate_docs_async(...)`.
- Оставить `generate_docs(...)` как sync wrapper.
- Не ломать существующий CLI.

Проверка:
- тест прямого вызова async API.

### 3.2 TLS verification и закрытие LLM client

Файлы:
- `ai_docs/llm.py`
- `ai_docs/cli.py`, `cli_prdiff.py`, `cli_watch.py` при необходимости
- tests
- README для новых env/settings

Работы:
- `verify=True` по умолчанию.
- Добавить явный insecure opt-in env, например `AI_DOCS_INSECURE_SSL=true`, с предупреждением.
- Добавить `async aclose()`/context manager у `LLMClient`.
- Закрывать клиент после генерации в CLI.
- Тесты: default verify true через fake client construction или patch `httpx.AsyncClient`; insecure opt-in передается явно; `aclose()` вызывает закрытие.

Проверка:
- LLM tests.

### 3.3 `watch` без перекрывающихся генераций

Файлы:
- `ai_docs/cli_watch.py`
- tests, вероятно `tests/test_cli.py` или `tests/test_watch.py`

Работы:
- Добавить single-flight lock/pending flag.
- Если событие пришло во время генерации, выполнить ровно один повтор после завершения.
- Не переиспользовать async primitives между разными event loops/threads небезопасно.

Проверка:
- unit test debouncer/runner без реального watchdog и LLM.

## Волна 4. P2 config/cache/dependencies/testing

### 4.1 Явная конфигурация вместо глобального process state

Файлы:
- `ai_docs/prompts.py`
- `ai_docs/site_config.py`
- `ai_docs/generator.py`
- `ai_docs/generator_sections.py`
- `ai_docs/cli.py`, `cli_prdiff.py`, `cli_watch.py`
- tests

Работы:
- Ввести `GenerationConfig` или близкий dataclass.
- Передавать `prompt_store`, `source_url`, `regen_sections` явно.
- Сохранить обратную совместимость для существующих tests, где это разумно.

Проверка:
- tests на независимые два запуска с разными prompt/source_url в одном процессе.

### 4.2 Config validation без молчаливого fallback

Файлы:
- `ai_docs/scanner.py`
- `ai_docs/prompts.py`
- `ai_docs/site_config.py`
- возможно новый `ai_docs/config.py`
- tests

Работы:
- Единый loader `.ai-docs.yaml`.
- Некорректный YAML должен давать понятную ошибку.
- Если legacy tolerant mode нужен для существующих путей, сделать явный opt-in.

Проверка:
- tests на invalid YAML для scanner/prompts/source_url.

### 4.3 Кэш: атомарная запись и единая политика ошибок

Файлы:
- `ai_docs/cache.py`
- tests/test_cache.py

Работы:
- Атомарная запись JSON.
- `index.json` и `llm_cache.json` обрабатываются одинаково.
- Битый кэш не должен молча сбрасываться; ошибка должна быть понятной.

Проверка:
- tests на corrupt index/cache.

### 4.4 Dependencies/testing sections для PEP 621 и pytest

Файлы:
- `ai_docs/generator_shared.py`
- tests

Работы:
- Читать `[project].dependencies` и `[project.optional-dependencies]`.
- Учитывать `requirements.txt`.
- Для Python-проекта с `tests/` и pytest выводить `pytest -q`.

Проверка:
- unit tests для `collect_dependencies()` и `collect_test_info()`.

### 4.5 Хэш по bytes, content для LLM отдельно

Файлы:
- `ai_docs/scanner.py`
- `ai_docs/generator_cache.py`
- `ai_docs/utils.py`
- tests

Работы:
- Считать hash по исходным bytes.
- Декодировать content отдельно.
- Не проглатывать decode-проблемы без metadata/сообщения.

Проверка:
- test: два файла с разными invalid bytes не схлопываются в одинаковый hash.

### 4.6 Синхронизация dependencies

Файлы:
- `pyproject.toml`
- `requirements.txt`
- README
- tests/test_packaging.py при необходимости

Работы:
- Добавить прямой `httpx`.
- Удалить или обосновать `requests`.
- Синхронизировать `mkdocs-material`.
- Добавить optional extra для `watchdog`.

Проверка:
- packaging test.

## Волна 5. P3 consolidation

### 5.1 Единый источник scan/domain rules

Файлы:
- `ai_docs/domain.py`
- `ai_docs/scanner.py`
- tests

Работы:
- Свести extensions, exact filenames, path markers и fixed include patterns в один модуль/структуру.
- Убрать дубли, сохранив публичное поведение.

Проверка:
- scanner/domain tests.

## Волна 6. Документация и codebase map

Файлы:
- `README.md`
- `README_EN.md` при необходимости
- `.cli-proxy/.codebase_map/nodes/*.md`

Работы:
- Описать пользовательские изменения: fail-fast, read-only scan, watch extra, TLS insecure opt-in, async API при необходимости.
- Обновить `Last reviewed` в nodes, затронутых изменениями: `ai-docs.md`, `tests.md`, `pyproject-toml.md`, возможно `run-docs-bg-sh.md`/`mkdocs-yml.md`.

Проверка:
- README содержит новые флаги/поведение.
- Nodes updated.

## Финальный gate

1. `pytest -q`
2. `ruff check ai_docs tests`
3. code-review сабагент по полному diff.
4. Если есть ошибки/предупреждения: исправить, повторить tests/Ruff/review.
5. После чистого результата закрыть `/goal` как complete.

## Статус выполнения

Обновлено: 2026-07-02.

- [x] Волна 0: план зафиксирован; предварительные планы подготовлены сабагентами A/B/C/D.
- [x] Волна 1: exit code для `python -m ai_docs`, fatal `GenerationError`, безопасный full-scan `pr-diff`.
- [x] Волна 2: `.github/workflows` включён в scan, `scan_source()` read-only, пути generated pages и `_index.json` унифицированы.
- [x] Волна 3: публичный `generate_docs_async`, TLS verification по умолчанию, `LLMClient.aclose()`, single-flight watch.
- [x] Волна 4: `GenerationConfig`, строгий config/env loader, атомарный кэш, PEP 621/testing deps, byte-hash, dependency sync.
- [x] Волна 5: `domain_rules.py` как единый источник scan/domain rules.
- [x] Волна 6: README/README_EN и codebase map обновлены.
- [x] Финальный gate: полный `pytest -q`, Ruff и повторяемый code-review сабагент до чистого результата.
