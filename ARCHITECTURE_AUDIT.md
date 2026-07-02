# Архитектурный аудит ai-docs

Дата: 2026-07-02

## Область анализа

Проверены основные слои проекта:

- CLI: `ai_docs/cli.py`, `ai_docs/__main__.py`, `ai_docs/cli_lint.py`, `ai_docs/cli_watch.py`, `ai_docs/cli_prdiff.py`
- сканирование и классификация: `ai_docs/scanner.py`, `ai_docs/domain.py`
- генерация: `ai_docs/generator.py`, `ai_docs/generator_cache.py`, `ai_docs/generator_summarize.py`, `ai_docs/generator_sections.py`, `ai_docs/generator_output.py`
- LLM, промпты, кэш: `ai_docs/llm.py`, `ai_docs/prompts.py`, `ai_docs/cache.py`, `ai_docs/summary.py`
- вывод MkDocs и индекс: `ai_docs/mkdocs.py`, `ai_docs/generator_shared.py`
- упаковка и тесты: `pyproject.toml`, `requirements.txt`, `MANIFEST.in`, `tests/`

Функциональные изменения в код не вносились. Найденные проблемы и предложения зафиксированы ниже.

## Текущая архитектура

Фактический поток выглядит так:

```text
CLI/subcommands
  -> scan_source()
  -> from_env() / LLMClient
  -> generate_docs()
     -> diff_files()
     -> summarize_entries()
     -> build_sections()
     -> write_docs()/write_readme()/build_mkdocs()
```

Основная идея простая и рабочая: сканер строит список файлов, генератор сравнивает его с кэшем, LLM обновляет summaries, затем из summaries собираются Markdown-страницы и MkDocs-сайт. Главные архитектурные риски сейчас не в общей схеме, а в стыках: CLI exit codes, частичные сканы, глобальное состояние процесса, кэш/индекс и скрытые fallback-пути.

## Найденные проблемы

### P0. `python -m ai_docs` теряет ненулевые exit codes

Доказательства:

- `ai_docs/__main__.py:21-22` вызывает `main()`, но не передает результат в `sys.exit(...)`.
- `ai_docs/cli_lint.py:37-42` корректно возвращает `2`, если нет `index.json`.
- Проверка в текущей среде показала: `python -m ai_docs lint --source <tmpdir>` печатает ошибку отсутствующего индекса, но процесс завершается с `rc=0`.

Влияние: CI, pre-commit и shell-скрипты могут считать проваленный `lint` успешным. Это ломает назначение команды `lint`.

Предложение: заменить финальный вызов на `sys.exit(main())` и добавить subprocess-тест для `python -m ai_docs lint --source <tmpdir>` с ожидаемым кодом `2`.

### P0. Ошибки LLM-суммаризации превращаются в успешную частичную генерацию

Доказательства:

- `ai_docs/generator_summarize.py:73-75` ловит любое исключение на файле и добавляет строку в `errors`.
- `ai_docs/generator.py:139-142` только печатает `errors summary`, не завершает генерацию ошибкой.
- `ai_docs/cli.py:186-198` не получает сигнал о частичном провале.

Влияние: пользователь получает обновленную документацию и exit code 0, хотя часть файлов могла не попасть в summaries. Это скрытая деградация результата.

Предложение: по умолчанию fail-fast или fail-after-phase: собрать ошибки по файлам, завершить команду ненулевым кодом и не перезаписывать финальные артефакты как успешные. Если частичная генерация действительно нужна, сделать ее явным режимом вроде `--allow-partial` с отчетом.

### P0. `pr-diff` может принять все неотсканированные файлы за удаленные

Доказательства:

- `ai_docs/cli_prdiff.py:58-73` сужает scan до файлов из `git diff`.
- `ai_docs/generator.py:43-45` строит `file_map` только из переданных файлов и запускает обычный diff.
- `ai_docs/cache.py:59-61` считает удаленными все пути из старого индекса, которых нет в текущем `file_map`.
- `ai_docs/generator.py:88-91` запускает cleanup для `deleted`.

Влияние: при наличии полного кэша `pr-diff` может удалить summaries для неизмененных файлов или записать неверный changes report.

Предложение: `pr-diff` должен делать полный scan для актуального `file_map`, а список changed paths использовать только как фильтр для повторной LLM-суммаризации. Альтернатива: отдельный режим diff, который merge-ит partial scan со старым индексом и не считает отсутствующие пути удаленными.

### P1. CI-домены декларированы, но `.github/workflows` физически исключены сканером

Доказательства:

- `ai_docs/domain.py:96-98` и `ai_docs/domain.py:161-162` умеют определять `.github/workflows` как CI.
- `ai_docs/scanner.py:41` исключает `.github/*`.
- `ai_docs/scanner.py:62` добавляет `.github` в prunable directories, поэтому walker туда не зайдет.

Влияние: GitHub Actions workflows не попадут в документацию, хотя README обещает CI/CD detection.

Предложение: убрать `.github` из безусловного pruning. Исключать точечно ненужные payload-файлы, но оставить `.github/workflows/*.yml|*.yaml`. Добавить тест на scan GitHub Actions workflow.

### P1. `_index.json` содержит неверные пути модулей

Доказательства:

- `ai_docs/generator_sections.py:303-304` генерирует module page path через `.replace(".", "__")`, например `modules/ai_docs/cli__py.md`.
- `ai_docs/generator_shared.py:183-184` строит путь для `_index.json` как `modules/ai_docs/cli.md`.

Влияние: навигационный индекс указывает на несуществующие страницы. Это особенно критично для `documentary.skill`, который должен полагаться на `.ai-docs/_index.json`.

Предложение: вынести построение путей страниц в один helper, например `module_doc_path(source_path)`, и использовать его в `generator_sections.py`, `generator_shared.py`, `mkdocs.py` и тестах.

### P1. `_index.json` строится до удаления orphan-документов

Доказательства:

- `ai_docs/generator_output.py:28-31` создает `_index.json` до cleanup.
- `ai_docs/generator_output.py:33-70` после этого может удалить orphan `.md` файлы.

Влияние: `_index.json` может содержать файлы, которые уже удалены тем же запуском.

Предложение: поменять порядок: сначала вычислить keep-set и cleanup, затем строить `_index.json` из финального набора файлов. Минимальный вариант - пересчитать `docs_index` после cleanup перед записью `_index.json`.

### P1. Сканирование имеет побочный эффект: создает `.ai-docs.yaml`

Доказательства:

- `ai_docs/scanner.py:117-127` пишет `.ai-docs.yaml`, если файл отсутствует.
- `scan_source()` используется не только генерацией, но и `lint`, `watch`, `pr-diff`.

Влияние: команды проверки могут менять чужой репозиторий. Для `lint` это особенно неожиданно: команда с семантикой проверки становится write-командой.

Предложение: сделать создание `.ai-docs.yaml` явным действием (`ai-docs init-config`) или параметром генерации. `scan_source()` должен быть read-only.

### P1. Глобальное состояние процесса делает генератор нерентерабельным

Доказательства:

- `ai_docs/prompts.py:232-242` хранит активный prompt store в глобальной переменной.
- `ai_docs/site_config.py:19-28` хранит `source_url` глобально.
- `ai_docs/cli.py:184-185` пишет `AI_DOCS_REGEN` в `os.environ`, а `ai_docs/generator.py:35-36` читает его из env.

Влияние: два запуска в одном процессе могут влиять друг на друга. Это опасно для `watch`, будущего API/сервиса и тестов, где порядок запуска начинает иметь значение.

Предложение: ввести `GenerationConfig`/`RuntimeConfig` dataclass и передавать `prompt_store`, `source_url`, `regen_sections`, `local_site`, `language` через параметры. Env читать только на CLI-границе.

### P1. `watch` может запускать перекрывающиеся генерации

Доказательства:

- `ai_docs/cli_watch.py:66-91` debouncer отменяет только еще не сработавший timer.
- `ai_docs/cli_watch.py:118-122` запускает `_regen` без блокировки "уже идет генерация".
- `ai_docs/cli_watch.py:115` создает один `LLMClient`, который переиспользуется в последующих `generate_docs()` вызовах.
- `ai_docs/generator.py:158-172` каждый раз создает новый event loop через `asyncio.run(...)`.

Влияние: при частых изменениях следующая генерация может начаться до завершения предыдущей. Переиспользование async locks/semaphores и клиента между разными event loop/threads повышает риск race conditions.

Предложение: сделать single-flight worker: один поток/цикл генерации, флаг pending, повторный запуск только после завершения текущего. LLM-клиент создавать и закрывать внутри того же async-контекста или перевести watch на один long-lived event loop.

### P1. Нет публичного async API генерации

Доказательства:

- `ai_docs/generator.py:22-34` содержит внутренний `_generate_docs_async`.
- `ai_docs/generator.py:145-172` экспортирует только синхронный `generate_docs()`, который делает `asyncio.run(...)`.

Влияние: генератор трудно использовать из уже async-приложения, бота, web-сервиса или тестового harness без nested event loop проблемы.

Предложение: экспортировать `async def generate_docs_async(...)` как поддерживаемый API, а sync `generate_docs()` оставить тонкой CLI-оберткой.

### P1. TLS verification отключен по умолчанию

Доказательства:

- `ai_docs/llm.py:33` создает `httpx.AsyncClient(verify=False)`.

Влияние: все LLM-запросы допускают MITM. Для self-signed endpoint это может быть нужно, но текущая реализация отключает проверку без явного выбора пользователя.

Предложение: `verify=True` по умолчанию. Для нестандартных CA добавить явный параметр/env вроде `OPENAI_CA_BUNDLE` или `AI_DOCS_INSECURE_SSL=true` с предупреждением.

### P1. Async HTTP client не закрывается явно

Доказательства:

- `ai_docs/llm.py:33-37` создает `httpx.AsyncClient` и передает его в `AsyncOpenAI`.
- В `LLMClient` нет `close/aclose`, context manager или cleanup в CLI/watch.

Влияние: в коротком CLI это может быть незаметно, но в `watch` и embedded-режимах возможны утечки соединений и warnings о незакрытых клиентах.

Предложение: добавить `async aclose()` в `LLMClient`, закрывать OpenAI/httpx клиент в `finally`, и использовать async context manager в генераторе или CLI.

### P2. Зависимости расходятся между `pyproject.toml` и `requirements.txt`

Доказательства:

- `ai_docs/llm.py:6` напрямую импортирует `httpx`, но `pyproject.toml:11-22` и `requirements.txt` не объявляют `httpx` явно.
- `pyproject.toml:13` объявляет `requests`, но в `ai_docs/**` он не используется.
- `requirements.txt` содержит `mkdocs-material`, а `pyproject.toml` нет.
- `watchdog` нужен для `ai-docs watch` (`ai_docs/cli_watch.py:96-102`), но не объявлен как optional extra.

Влияние: локальная разработка и пакетная установка могут получать разные окружения. Прямые импорты через транзитивные зависимости хрупкие.

Предложение: выбрать один источник правды. Практичный вариант: держать runtime dependencies в `pyproject.toml`, `requirements.txt` генерировать/синхронизировать из него, добавить extras `watch = ["watchdog"]`, удалить неиспользуемый `requests` или подтвердить его назначение.

### P2. Кэш пишется неатомарно и обрабатывается непоследовательно

Доказательства:

- `ai_docs/cache.py:18` читает `index.json` без обработки `JSONDecodeError`.
- `ai_docs/cache.py:29-37` при битом `llm_cache.json` молча сохраняет `.bad` и возвращает пустой кэш.
- `ai_docs/cache.py:20-21` и `ai_docs/cache.py:39-41` пишут JSON напрямую в целевой файл.

Влияние: прерывание процесса может повредить кэш. Один файл кэша упадет, другой будет молча проигнорирован и вызовет дорогую повторную генерацию.

Предложение: атомарная запись через temp file + rename. Для чтения - единая политика: fail с понятной ошибкой или явный `--repair-cache`; не молчаливый fallback.

### P2. Автоматический `regen all` для малых проектов скрыт от пользователя

Доказательства:

- `ai_docs/generator_sections.py:143-151` добавляет `all`, если `module_count < AI_DOCS_REGEN_ALL_THRESHOLD`.

Влияние: запуск без `--regen all` может перегенерировать больше разделов, чем ожидается. Это влияет на стоимость LLM, время и diff сгенерированных файлов.

Предложение: сделать поведение явным CLI/config-параметром или как минимум печатать предупреждение до LLM-вызовов и документировать настройку в README.

### P2. Генерация dependency/testing sections не учитывает текущий packaging style

Доказательства:

- `ai_docs/generator_shared.py:43-48` для `pyproject.toml` читает только `tool.poetry.dependencies`.
- Текущий `pyproject.toml:5-22` использует PEP 621 `[project].dependencies`.
- `ai_docs/generator_shared.py:64-89` ищет Poetry scripts, `setup.cfg`, `tox.ini` или `package.json`, но для текущего Python-проекта с pytest команда не определяется.

Влияние: сгенерированные разделы "Зависимости" и "Тестирование" могут быть неполными даже для самого проекта `ai-docs`.

Предложение: добавить поддержку `[project].dependencies`, `[project.optional-dependencies]`, `requirements.txt`, а для Python-проектов с каталогом `tests/` и pytest-зависимостью выводить `pytest -q`.

### P2. Конфигурационные ошибки часто скрываются

Доказательства:

- `ai_docs/scanner.py:129-135` при некорректном `.ai-docs.yaml` возвращает defaults.
- `ai_docs/prompts.py:216-224` при некорректном YAML/типе возвращает пустые overrides.
- `ai_docs/site_config.py:35-44` при некорректном YAML возвращает `None`.

Влияние: пользователь может думать, что настройки применены, хотя генератор работает с defaults.

Предложение: единый загрузчик конфигурации с валидацией и явными ошибками. Для legacy-совместимости можно оставить `--ignore-config-errors`, но только как opt-in.

### P2. Хэш файла считается по lossy UTF-8 декодированному тексту

Доказательства:

- `ai_docs/utils.py:13-14` читает текст с `errors="ignore"`.
- `ai_docs/generator_cache.py:20-21` считает hash по `f["content"]`.

Влияние: байтовые изменения в не-UTF-8 файлах могут быть потеряны при декодировании, а diff будет менее надежным.

Предложение: хранить `content` как декодированный текст для LLM, но `hash` считать по исходным bytes. Ошибки декодирования фиксировать в metadata/логах.

### P3. Дублируется знание о типах файлов и include patterns

Доказательства:

- `ai_docs/domain.py:5-88` содержит extension maps.
- `ai_docs/scanner.py:23-28` содержит отдельный `FIXED_INCLUDE_PATTERNS`.
- `ai_docs/scanner.py:150-154` объединяет extension config с fixed patterns.

Влияние: легко добавить поддержку домена в одном месте и забыть включение/исключение в другом. Пример уже есть с `.github/workflows`.

Предложение: собрать правила сканирования в одну структуру: extensions, exact filenames, path markers, default excludes. Domain detection и scanner должны читать один источник.

## Архитектурные предложения

### Вариант A: Минимальное укрепление текущей архитектуры

Суть: оставить текущие модули, но закрыть критические стыки.

Что сделать:

1. Исправить `__main__.py` и добавить subprocess-тест exit code.
2. Сделать ошибки суммаризации фатальными по умолчанию.
3. Исправить `pr-diff`: полный scan + changed mask.
4. Централизовать функции путей для module/config pages и пересобрать `_index.json` после cleanup.
5. Включить `.github/workflows` в scan.
6. Включить TLS verification и явный insecure opt-in.

Плюсы: быстро, низкий риск, хорошо ложится на текущий код.

Минусы: глобальное состояние и sync/async граница останутся техническим долгом.

### Вариант B: Явная модель pipeline

Суть: оформить промежуточные данные как typed pipeline:

```text
ScanSnapshot -> DiffPlan -> SummaryPlan -> DocsPlan -> WriteResult
```

Что меняется:

- `pr-diff`, `lint`, `gen`, `watch` используют один и тот же `ScanSnapshot`.
- `DiffPlan` явно различает `changed`, `unchanged`, `deleted`, `forced`, `partial`.
- Cleanup работает только после успешного `DocsPlan`.
- `_index.json` строится из финального `WriteResult`.

Плюсы: меньше скрытых связей, проще тестировать, `pr-diff` перестает быть специальным опасным путем.

Минусы: больше рефакторинга, нужен аккуратный миграционный план.

### Вариант C: Library-first generator

Суть: сделать `ai_docs` в первую очередь библиотекой с чистым async API, а CLI - тонкой оболочкой.

Что меняется:

- `GenerationConfig` передается явно, без process globals.
- `generate_docs_async()` становится публичным API.
- `LLMClient` становится async context manager.
- `watch` работает через один event loop и очередь событий.

Плюсы: устойчиво для ботов, web-сервисов, long-running режимов и тестов.

Минусы: больше изменений публичных контрактов; нужно сохранить обратную совместимость CLI.

## Рекомендуемый порядок работ

1. P0-gate: `__main__.py`, fatal errors для LLM, безопасный `pr-diff`.
   Проверка: subprocess tests + pytest.

2. Индекс и scanner consistency: единый path helper, `_index.json` после cleanup, `.github/workflows` scan.
   Проверка: unit tests на реальные generated paths и GitHub Actions workflow.

3. Runtime safety: TLS verify, закрытие LLM client, no-overlap watch.
   Проверка: mocked LLM/client tests и watch debounce test без реального API.

4. Конфигурация и зависимости: явный `GenerationConfig`, единый config loader, синхронизация pyproject/requirements.
   Проверка: config validation tests и packaging tests.

5. Pipeline model: выделить `ScanSnapshot`, `DiffPlan`, `DocsPlan`.
   Проверка: тесты diff/pr-diff/cleanup без LLM.

## Что не стоит делать сейчас

- Не стоит переписывать генератор целиком: текущая схема понятная, а критические дефекты находятся в стыках.
- Не стоит добавлять новые fallback-режимы для конфигов/LLM. Лучше явные ошибки и отдельные opt-in flags.
- Не стоит чинить только README: часть проблем проверяется кодом и влияет на CI/runtime.

## Минимальные тесты для первого PR

- `python -m ai_docs lint --source <tmpdir>` возвращает `2`, если нет кэша.
- `summarize_entries()` с ошибкой LLM приводит к ненулевому результату `gen` и не маскируется успешной генерацией.
- `pr-diff` на репозитории с двумя файлами и изменением одного файла не помечает второй файл удаленным.
- scan включает `.github/workflows/build.yml`.
- `_index.json` module path совпадает с реально созданным `modules/**/*.md`.
- cleanup не оставляет в `_index.json` удаленные orphan-файлы.
