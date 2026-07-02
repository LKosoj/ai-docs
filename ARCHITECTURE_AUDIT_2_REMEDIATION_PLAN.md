# План доработки по ARCHITECTURE_AUDIT_2.md

Дата: 2026-07-02

## Цель

Закрыть все пункты из `ARCHITECTURE_AUDIT_2.md`: P1, P2, P3 и архитектурные предложения A-E.
Работы идут по приоритету, но независимые проверки и подготовка планов выполняются параллельно.

## Принятые допущения

- "Все пункты аудита" означает не только минимальный первый PR, а полный список P1/P2/P3 и A-E.
- Публичный CLI-контракт должен сохраниться, кроме явно исправляемых дефектов (`ai-docs help`, `--exclude`).
- Новые fallback-режимы не добавляются. Legacy fallback остаётся только если он уже был частью поведения и явно логируется.
- Каждое изменение поведения получает regression-тест.
- После каждой крупной волны запускаются targeted tests, перед финалом - `pytest -q` и `ruff check`.
- Финальный gate: code-review subagent, исправление всех ошибок и предупреждений, повтор ревью до чистого результата.

## Subagent-распределение

- `architect/P1 planner`: детальный план P1, write-set, риски и тесты.
- `architect/P2 planner`: детальный план P2, независимые группы и конфликтующие файлы.
- `architect/P3+A-E planner`: детальный план P3 и архитектурных предложений.
- `python-dev worker`: реализация выделенных задач с непересекающимся write-set.
- `tester`: проверка покрытия и предложения дополнительных regression-тестов после каждой волны.
- `reviewer`: ревью после каждой завершённой задачи/волны и финальный повторяемый gate.

## Волна 0. Подготовка

1. Зафиксировать этот план.
   Проверка: файл существует и покрывает все пункты аудита.
2. Сверить subagent-планы с текущим планом.
   Проверка: нет пропущенных пунктов, write-set конфликтов или неявных fallback.
3. Зафиксировать baseline.
   Проверка: `pytest -q` и `ruff check ai_docs tests` либо явно указать исходные проблемы.

## Волна 1. P1 - корректность генерации

### P1-1. `_needs_doxygen_fix` не должен падать на строке из одной цифры

Файлы:
- `ai_docs/summary.py`
- `tests/test_summary.py`

Работы:
- Заменить индексирование `stripped[1]` на безопасную проверку нумерованного списка.
- Предпочтительно использовать маленький helper или regex `^\d+\.` без лишней абстракции.

Тесты:
- `"5"` не бросает исключение и не требует reformat.
- `"1. пункт"` детектируется как список.

Критерий готовности: targeted summary tests зелёные.

### P1-5. LLM boundary: не кэшировать `None` и обрезанные ответы

Файлы:
- `ai_docs/llm.py`
- `tests/test_llm.py`

Работы:
- Проверять наличие `choices[0]`, `message.content` и тип `str`.
- Требовать непустой `content.strip()`.
- Проверять `finish_reason`: валидным считать `None` или `"stop"` для совместимости с test doubles; `"length"` и другие явные причины считать ошибкой.
- Кэшировать только валидный ответ.
- Удалить недостижимый `for..else`.

Тесты:
- `content=None` даёт понятный `RuntimeError` и не пишет ключ в cache.
- `finish_reason="length"` даёт понятный `RuntimeError` и не пишет ключ в cache.
- валидный ответ кэшируется как раньше.

Критерий готовности: targeted LLM tests зелёные.

### P1-4. Ошибки LLM в секциях должны стать `GenerationError`

Файлы:
- `ai_docs/generator.py`
- `ai_docs/generator_sections.py`
- `tests/test_generator.py`

Работы:
- Обернуть вызов `build_sections` в `generate_docs_async`.
- При ошибке секций бросать `GenerationError` с контекстом, не писать docs/build/index.
- В `build_sections` при `section_tasks` использовать controlled gather: при первой ошибке отменять незавершённые задачи и дожидаться отмены через `return_exceptions=True`.

Тесты:
- Fake LLM падает на фазе секций, `generate_docs_async` бросает `GenerationError`.
- `write_docs`, `write_readme`, `build_mkdocs` не вызываются.

Критерий готовности: generator tests зелёные, CLI не показывает сырой traceback для `GenerationError`.

### P1-3. `watch` не должен реагировать на собственные артефакты

Файлы:
- `ai_docs/cli_watch.py`
- `tests/test_watch.py`

Работы:
- Вынести predicate для фильтрации событий, чтобы тестировать без watchdog.
- Исключать абсолютные пути генерации: cache dir, `.ai-docs/`, `ai_docs_site/`, `mkdocs.yml`, `README.md`.
- Разрешить `.github/**` для P3-3 в той же точке фильтра.

Тесты:
- `mkdocs.yml`, `README.md`, `.ai-docs/index.md`, `ai_docs_site/index.html` не вызывают `bump`.
- `.github/workflows/build.yml` вызывает `bump`.

Критерий готовности: watch tests зелёные.

### P1-2. Кодовые файлы не должны терять `type="code"` из-за доменных маркеров

Файлы:
- `ai_docs/domain.py`
- `ai_docs/scanner.py`
- `tests/test_scanner.py`
- возможно `ai_docs/domain_rules.py`

Работы:
- Сопоставлять доменные маркеры по сегментам пути, а не подстрокой всего пути.
- Не переопределять `type` для файлов с кодовыми расширениями; домены остаются метками.
- Сохранить явные infra/ci случаи: Dockerfile, Terraform, CI workflows.

Тесты:
- `app/tasks/worker.py`, `app/gateway/api.py`, `src/s3util/helper.py` остаются `type="code"`.
- Инфраструктурные файлы сохраняют прежнюю классификацию.
- Кодовый файл получает module summary через существующую генераторную ветку.

Критерий готовности: scanner/generated docs tests зелёные.

## Волна 2. P2 - CLI, ресурсы, упаковка

### P2-1. `dependencies.md` не должен деградировать на кэшированном прогоне

Файлы:
- `ai_docs/generator_sections.py`
- `tests/test_generated_docs.py`

Работы:
- Если `dependencies.md` не перегенерирован, не перезаписывать его только блоком зависимостей.
- Если файл новый или forced, добавлять блок "Выявленные зависимости".
- Не дублировать блок при повторных прогонах.

Тесты:
- Два последовательных `build_sections` сохраняют LLM-часть `dependencies.md`.

### P2-2. `--exclude` должен дополнять дефолтные исключения

Файлы:
- `ai_docs/scanner.py`
- `README.md`
- `README_EN.md`
- `tests/test_scanner.py`

Работы:
- В `scan_source` и `path_in_scan_scope` строить `DEFAULT_EXCLUDE_PATTERNS | user_exclude | config_exclude`.
- Не добавлять новый флаг полной замены, если он не нужен текущему запросу.

Тесты:
- `scan_source(exclude={"*.log"})` не включает `mkdocs.yml`.
- Пользовательский `*.log` всё ещё исключается.

### P2-3. `lint` должен явно отказываться от URL и не оставлять tmpdir при scan error

Файлы:
- `ai_docs/cli_lint.py`
- `ai_docs/scanner.py`
- `tests/test_cli.py`
- возможно `tests/test_scanner.py`

Работы:
- В `run_lint` вернуть rc=2 для URL до `scan_source`.
- В URL-ветке `scan_source` очищать tmpdir при исключении после clone.

Тесты:
- `run_lint` на URL возвращает 2 без вызова `scan_source`.
- Ошибка `_scan_directory` после clone удаляет tmpdir.

### P2-4. Tokenizer cache не должен держать полные тексты без лимита

Файлы:
- `ai_docs/tokenizer.py`
- `tests/test_performance.py` или новый tokenizer test

Работы:
- Убрать `lru_cache` с ключом-полным текстом для `_encode_tokens` и `_chunk_text_cached`.
- Оставить кэш только для encoding object.
- Для `count_tokens` считать длину напрямую без materialized tuple.

Тесты:
- `count_tokens` и `chunk_text` сохраняют контракт.
- В модуле нет `_encode_tokens.cache_info`/large text lru path.

### P2-5. `requires-python` привести к реальному рантайму

Файлы:
- `pyproject.toml`
- `README.md`
- `README_EN.md`
- `.cli-proxy/.codebase_map/STACK.md` при необходимости
- `tests/test_packaging.py`

Работы:
- Поднять `requires-python` до `>=3.10`.
- Обновить документацию.
- Снять устаревший тест, запрещающий builtin generics для Python 3.9, или заменить на проверку `requires-python`.

Тесты:
- packaging test проверяет `>=3.10`.

### P2-6. Устаревшие paginated-страницы должны удаляться

Файлы:
- `ai_docs/generator_output.py`
- `tests/test_generated_docs.py`

Работы:
- Не добавлять все существующие `modules/page-*.md` и `configs/page-*.md` в keep-set.
- Оставлять только страницы из текущего `docs_files`.

Тесты:
- Если раньше был `modules/page-2.md`, а текущая генерация даёт только `modules/index.md`, `page-2.md` удаляется и не попадает в `_index.json`.

### P2-7. `ai-docs help` должен возвращать rc=0

Файлы:
- `ai_docs/cli.py`
- `tests/test_cli.py`

Работы:
- Маппить `help` на `--help` в `_normalize_argv` или добавить parser alias.

Тесты:
- subprocess `python -m ai_docs help` возвращает 0 и содержит usage.

## Волна 3. P3 - малые дефекты и технический долг

### P3-1. MkDocs nav должен использовать `DOMAIN_TITLES`

Файлы:
- `ai_docs/mkdocs.py`
- `tests/test_generated_docs.py` или mkdocs test

Работы: импортировать `DOMAIN_TITLES` из `generator_shared` и убрать локальный partial map.

Тест: `service_mesh` отображается как `Service Mesh / Ingress`.

### P3-2. Точки в каталогах не должны калечиться

Файлы:
- `ai_docs/generator_shared.py`
- `ai_docs/mkdocs.py`
- `tests/test_generated_docs.py`

Работы:
- Заменять `.` только в имени файла generated page, не во всех сегментах пути.
- Сохранить обратимость последнего сегмента в nav.

Тест: `module_doc_path("src/v1.2/mod.py")` сохраняет каталог `v1.2`, добавляет стабильный суффикс-хэш к имени файла и nav содержит `/v1.2`.

### P3-3. `watch` должен учитывать `.github/**`

Закрывается вместе с P1-3.

### P3-4. `llm_cache.json` должен иметь ограничение роста

Файлы:
- `ai_docs/cache.py`
- `ai_docs/generator_cache.py`
- `ai_docs/llm.py`
- tests

Работы:
- Хранить LLM cache как dict с ограничением количества записей при сохранении.
- Без миграции формата, чтобы не ломать существующий cache.
- Консервативный default, например 5000 записей, через env `AI_DOCS_LLM_CACHE_MAX_ENTRIES`.

Тесты:
- `save_llm_cache` обрезает старые записи сверх лимита.
- Некорректный env даёт `ConfigError`.

### P3-5. Mermaid postprocess должен менять только mermaid-блоки

Файлы:
- `ai_docs/generator_output.py`
- `tests/test_performance.py`

Работы:
- Использовать regex/локальный parser по `<div class="mermaid"...>...</div>`.
- Не менять `&gt;` вне mermaid div.

Тест: файл с mermaid и обычным HTML сохраняет обычный `&gt;`.

### P3-6. Уменьшить повторное чтение конфигурации и файлов

Файлы:
- `ai_docs/scanner.py`
- `ai_docs/utils.py`
- tests

Работы:
- В `path_in_scan_scope` добавить необязательный prepared context или helper для повторного использования specs в `pr-diff`.
- В `_load_file_record` читать первый sample bytes из уже прочитанного файла либо заменить `is_binary_file + read_bytes` на single read with NUL check.
- Не делать широкий config cache без необходимости.

Тесты:
- Scanner сохраняет decode/hash поведение.
- pr-diff deleted filtering использует prepared scope без повторного YAML чтения (через mock).

### P3-7. Мелкие смеллы

Файлы:
- `ai_docs/generator_sections.py`
- `ai_docs/generator_output.py`
- `ai_docs/generator_cache.py`
- `ai_docs/mkdocs.py`
- `ai_docs/summary.py`
- `ai_docs/tokenizer.py`
- CLI modules

Работы:
- Переименовать `__serialize_index` в `_serialize_index`.
- Убрать локальные `import time` там, где файл уже импортирует или нужен top-level import.
- Убрать `changes_summary_holder` в пользу локального результата task.
- Убрать мёртвую ветку в `llm.py`.
- Связать chunk size summary с budget, если это можно сделать без смены публичного контракта; иначе оставить как tracked note в кодовом плане A/B.
- Не переписывать print/logging полностью до предложения E.

Тесты: существующие генераторные и performance tests.

## Волна 4. Архитектурные предложения A-E

### A. Library-first bootstrap

Файлы:
- новый `ai_docs/run_context.py` или минимально `ai_docs/cli_common.py`
- `ai_docs/cli.py`
- `ai_docs/cli_watch.py`
- `ai_docs/cli_prdiff.py`
- tests

Работы:
- Выделить `RunContext`: include/exclude, threads, scan_result, generation_config, output_root, llm lifecycle.
- Убрать дублирование `_close_llm` и common `scan -> config -> from_env -> generate_docs`.
- Сохранить sync CLI.

Тесты:
- gen/watch/pr-diff продолжают передавать одинаковые flags.
- LLM закрывается через общий helper.

### B. Декларативная модель секций

Файлы:
- `ai_docs/generator_sections.py`
- tests

Работы:
- Ввести маленький `SectionSpec` для обычных top-level sections.
- Перевести overview/index/domain/modules/configs/changes постепенно, начиная с top-level LLM sections.
- Не делать переписывание всей функции одним патчем без промежуточных зелёных тестов.

Тесты:
- forced/cached section behavior сохраняется.
- dependencies/modules/configs/changes regression tests зелёные.

### C. Валидация LLM-форматов

Файлы:
- `ai_docs/summary.py`
- `ai_docs/llm.py`
- tests

Работы:
- Для tagged summaries требовать непустой нужный tag, когда вызван bundle prompt.
- Ошибка формата должна быть явной, не пустым summary.

Тесты:
- Ответ без `<module_summary>` при module bundle падает понятной ошибкой.
- Ответ без `<config_summary>` при config bundle падает понятной ошибкой.

### D. Domain matching segments

Основная часть закрывается P1-2. Дополнительно:
- вынести segment helpers в `domain.py`;
- добавить тесты для настоящих infra путей и ложных code путей.

### E. Наблюдаемость

Файлы:
- новый `ai_docs/logging_utils.py` или минимальная настройка в `cli.py`
- основные CLI/generator modules
- README
- tests

Работы:
- Ввести `logging` с форматером `[ai-docs]`.
- Добавить `--verbose`/`--quiet` только если можно провести через common args без ломки.
- Перевести warning/fallback/insecure messages первыми; массовый перевод progress print делать после сохранения тестов.

Тесты:
- CLI принимает новые флаги.
- Warning о insecure/fallback виден через logging/caplog или mock.

## Финальный gate

1. `pytest -q`
2. `ruff check ai_docs tests`
3. `reviewer` subagent на весь diff.
4. Исправить все ошибки и предупреждения.
5. Повторять пункты 1-4 до чистого результата.
6. Обновить `Last reviewed` в релевантных codebase-map nodes:
   - `nodes/ai-docs.md`
   - `nodes/tests.md`
   - `nodes/pyproject-toml.md`
   - `nodes/mkdocs-yml.md`, если менялась MkDocs-навигация
