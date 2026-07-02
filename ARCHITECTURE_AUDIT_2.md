# Архитектурный аудит ai-docs — раунд 2

Дата: 2026-07-02.
Контекст: аудит №1 (`ARCHITECTURE_AUDIT.md`) закрыт ремедиацией в коммите `fbfedfb`
(«Добавлен асинхронный Python API, поддержка отключения проверки TLS и новые тесты»).
Этот документ — повторный аудит уже исправленного кода.

Методика: построчное чтение всех 25 модулей `ai_docs/**` (персоны reviewer + architect
из skill `dev-experts`), подтверждение гипотез исполнением кода в `.venv`,
прогон `pytest -q` (83 passed, 6 subtests) и `ruff check` (чисто).

## Статус находок аудита №1

Выборочно проверено по коду — все ключевые пункты действительно закрыты:

- exit codes: `ai_docs/__main__.py:22` — `sys.exit(main())`;
- fail-fast: `ai_docs/generator.py:24-37` — `GenerationError`, `_raise_if_summarization_failed`;
- безопасный `pr-diff`: `ai_docs/cli_prdiff.py` — полный скан + маски changed/deleted из `git diff --name-status -z`;
- `.github/workflows` сканируется (нет в `PRUNABLE_DIR_NAMES`/`DEFAULT_EXCLUDE_PATTERNS`);
- read-only `scan_source()` (автосоздание `.ai-docs.yaml` убрано);
- единые пути страниц: `generator_shared.py:40-45` — `module_doc_path`/`config_doc_path`;
- `_index.json` строится после cleanup (`generator_output.py:73-75`);
- TLS verify по умолчанию + `AI_DOCS_INSECURE_SSL` opt-in (`llm.py:145-157`);
- `LLMClient.aclose()`/context manager (`llm.py:43-55`), закрытие в CLI через `finally`;
- single-flight watch (`cli_watch.py:84-128`, `_Debouncer` с `_running`/`_pending`);
- `GenerationConfig` (`generation_config.py`), строгий config-loader (`config.py`), атомарный кэш (`cache.py:48-52`);
- PEP 621 deps + `requirements.txt` + pytest detection (`generator_shared.py:48-103`);
- hash по bytes (`scanner.py:143`, `sha256_bytes(raw)`), `decode_error` в metadata;
- зависимости синхронизированы (`httpx` объявлен, `requests` удалён, extras `watch`/`dev`);
- единый источник правил — `domain_rules.py`.

## Новые проблемы

### P1-1. `_needs_doxygen_fix` падает с IndexError на строке из одной цифры

Доказательства (подтверждено исполнением):

- `ai_docs/summary.py:26`: `if stripped[:2].isdigit() and stripped[1] == ".":`.
- Строка summary, состоящая из одной цифры (например, `"5"`): `stripped[:2]` = `"5"`,
  `.isdigit()` → True, затем `stripped[1]` → `IndexError: string index out of range`.
- Исключение всплывает из `summarize_file_outputs` → попадает в `errors` →
  `GenerationError`: падает вся генерация из-за одной строки в ответе LLM.

Вторая ошибка в той же строке: намерение было детектировать нумерованные списки
(`"1. пункт"`), но `stripped[:2]` для `"1."` возвращает `"1."`, что не `isdigit()` —
условие не срабатывает никогда (подтверждено: `_needs_doxygen_fix("Текст\n1. пункт")` → False).

Предложение: заменить на `stripped[:1].isdigit() and len(stripped) > 1 and stripped[1] == "."`
(или regex `^\d+\.`), добавить тесты: строка «5» не роняет функцию; «1. пункт» детектируется.

### P1-2. Substring-маркеры доменов реклассифицируют обычный код как infra и лишают его документации

Доказательства (подтверждено исполнением):

- `ai_docs/domain.py:69`: `"/tasks/" in posix_path` → домен `ansible`;
  `domain.py:82`: маркеры `gateway`, `ingress` → `service_mesh`;
  `domain.py:94`: маркеры `s3`, `redis`, `postgres` как подстроки → `data_storage`.
- `ai_docs/scanner.py:136-137`: если `is_infra(domains)`, `file_type` становится `"infra"`.
- Проверено: `app/tasks/worker.py` → `{'ansible'}`, `app/gateway/api.py` → `{'service_mesh'}`,
  `src/s3util/helper.py` → `{'data_storage'}` — все три получают `is_infra=True`.
- `generator_summarize.py:54`: module summary генерируется только для `type == "code"` →
  такие файлы теряют страницу модуля, выпадают из `modules/**`, `_index.json` и nav.

Влияние: в любом Celery/веб-проекте каталоги `tasks/`, `gateway/`, файлы с "s3"/"redis"
в пути документируются как инфраструктура без API-описания. Это тихая потеря контента.

Предложения:

1. Маркеры сопоставлять по сегментам пути (`part == "s3"`), а не подстрокой всего пути.
2. Не переопределять `type` для файлов с кодовым расширением: код остаётся `code`,
   домены — дополнительные метки (использовать в разделах доменов, но не терять module summary).
3. Тест: `app/tasks/worker.py` получает module summary.

### P1-3. `watch` с настройками по умолчанию сам себя триггерит (бесконечный цикл регенерации)

Доказательства:

- `ai_docs/cli_watch.py:70-71`: при запуске без флагов `write_mkdocs = (args.mkdocs or not args.readme)` → True.
- `generator_output.py:106`: `build_mkdocs` пишет `mkdocs.yml` в `output_root` (по умолчанию = source root)
  и запускает `mkdocs build`.
- `cli_watch.py:161-175`: фильтр обработчика исключает только `cache_dir`, `.git`, `ai_docs_site`
  и скрытые каталоги. `mkdocs.yml` (и `README.md` при `--force`) в корне не исключены.
- Итог: regen → запись `mkdocs.yml` → событие watchdog → `bump()` → новый regen → … Цикл
  ограничен только debounce; каждый виток — полный скан + `mkdocs build` (CPU/диск, возможны LLM-вызовы).

Предложение: исключить в обработчике продукты генерации: `mkdocs.yml`, `README.md`,
`.ai-docs/`, `ai_docs_site/`, cache dir — по абсолютным путям, вычисленным из `output_root`,
а не по именам. Тест: событие по `mkdocs.yml` не вызывает `bump()`.

### P1-4. Ошибки LLM в фазе генерации секций дают сырой traceback вместо контролируемого отказа

Доказательства:

- `ai_docs/llm.py:119`: неретраибельная ошибка → `RuntimeError("LLM request failed: ...")`.
- В `generator_sections.py` вызовы `generate_section`/`summarize_chunk`/`build_hierarchical_context`
  ничем не обёрнуты; `asyncio.gather(*section_tasks)` (`generator_sections.py:442`) пробрасывает
  первое исключение, остальные задачи не отменяются («Task exception was never retrieved» + лишние LLM-вызовы).
- `ai_docs/cli.py:256-261`: `main()` ловит только `GenerationError`, `ConfigError`, `CacheError` —
  `RuntimeError` из LLM пролетает наружу как traceback.

Влияние: fail-fast для summarization реализован (аудит №1), а для секций — нет:
пользователь получает stacktrace, частично записанные `docs_files` могут не совпадать
с сохранённым индексом.

Предложение: единообразно оборачивать фазу секций (перехватывать ошибки задач,
отменять остальные, собирать в `GenerationError`); в `main()` можно дополнительно
ловить `RuntimeError` от LLM с человекочитаемым сообщением. Тест: fake LLM падает
на секции → `GenerationError`, rc=1, без traceback.

### P1-5. `LLMClient.chat` кэширует `None` и обрезанные ответы навсегда

Доказательства:

- `ai_docs/llm.py:107`: `content = response.choices[0].message.content` — может быть `None`
  (пустой ответ провайдера) — валидации нет.
- `llm.py:128-130`: `cache[key] = content` без проверки → `null` попадает в `llm_cache.json`;
  при следующих запусках `llm.py:90-92` вернёт `None` из кэша → `.strip()` у вызывающих →
  `AttributeError` → `GenerationError`. Отказ становится «липким» до ручной чистки кэша.
- `finish_reason` не проверяется: ответ, обрезанный по `length`, кэшируется как валидный
  и навсегда остаётся в документации.

Предложение: валидировать ответ на границе (`content` непустой; `finish_reason == "stop"`,
иначе ошибка или повтор с увеличенным лимитом); кэшировать только валидные ответы.
Тест: ответ с `content=None` не попадает в кэш и даёт понятную ошибку.

## Проблемы P2

### P2-1. `dependencies.md` деградирует на каждом кэшированном прогоне

- `generator_sections.py:227-235`: секция `dependencies` не перегенерируется, если файл
  существует и не forced — в `docs_files` ключа нет.
- `generator_sections.py:452-455`: при непустых deps ключ создаётся заново из заголовка +
  списка зависимостей: `docs_files.get("dependencies.md", f"# {SECTION_TITLES['dependencies']}\n\n") + ...`.
- `generator_output.py:30`: `write_docs_files` пишет все `docs_files` → существующий
  `dependencies.md` с LLM-описанием перезаписывается урезанной версией при любом прогоне без `--regen`.

Предложение: если секция не перегенерируется — не трогать файл (или читать существующий
контент и обновлять только блок «Выявленные зависимости»). Тест: два прогона подряд
не меняют LLM-часть `dependencies.md`.

### P2-2. Пользовательский `--exclude` замещает дефолтные исключения, а не дополняет их

- `scanner.py:230`: `exclude = set(exclude or DEFAULT_EXCLUDE_PATTERNS)` — при любом
  `--exclude` дефолты исчезают.
- Подтверждено исполнением: со `--exclude '*.log'` в скан попадает `mkdocs.yml`
  (продукт генерации) → инструмент документирует собственные артефакты.
  Каталоги из `PRUNABLE_DIR_NAMES` (`.git`, `.venv`, `.ai-docs`, …) защищены pruning'ом,
  но файловые паттерны (`mkdocs.yml`, `.ai-docs.yaml`, `ai_docs/assets/*`) — нет.

Предложение: `--exclude` должен добавляться к `DEFAULT_EXCLUDE_PATTERNS`
(для полной замены — отдельный флаг `--no-default-excludes`). Отразить в README. Тест на объединение.

### P2-3. `lint` на URL-источнике клонирует репозиторий и утекает tmpdir

- `cli_lint.py:29-42`: нет проверки `is_url` (в отличие от `watch`/`pr-diff`);
  URL приводит к клонированию (`scanner.py:233`), `index.json` в клоне отсутствует → rc=2,
  а временный каталог никто не удаляет.
- Смежное: в `scan_source` при исключении внутри `_scan_directory` для URL-источника
  tmpdir тоже утекает (cleanup только в CLI `finally`).

Предложение: `lint` — явный отказ для URL (rc=2 с сообщением); в `scan_source`
обернуть URL-ветку в try/except с `shutil.rmtree` при ошибке.

### P2-4. Кэши токенизатора держат полные тексты файлов в памяти без ограничения объёма

- `tokenizer.py:26-29`: `@lru_cache(maxsize=2048)` на `_encode_tokens(text, model)` — ключ
  содержит весь текст файла (до 200 КБ), значение — кортеж int'ов (~28 байт на токен).
  Файл на 50k токенов ≈ 1.5 МБ на запись; 2048 записей — потенциально гигабайты.
- `tokenizer.py:32-40`: `_chunk_text_cached` — ещё 512 записей с полным текстом + чанками.

Предложение: кэшировать по хэшу текста либо ограничить размер кэшируемого значения;
для `count_tokens` не материализовывать кортеж (достаточно `len(enc.encode(text))` без кэша
или с кэшем «hash → int»).

### P2-5. Заявленный `requires-python = ">=3.8"` не соответствует реальному коду

- `pyproject.toml`: `requires-python = ">=3.8"`.
- `llm.py:35-36`: `asyncio.Lock()`/`asyncio.Semaphore()` создаются в `__init__` вне работающего
  event loop, а используются внутри `asyncio.run(...)` (другой loop). На Python 3.8/3.9
  примитивы привязываются к loop'у в конструкторе → «attached to a different loop» /
  «no current event loop in thread» (особенно в `watch`, где `LLMClient` создаётся в timer-потоке).
  Лениво примитивы привязываются только с 3.10+.

Предложение: поднять `requires-python` до фактически поддерживаемой версии (>=3.10,
а лучше проверить на минимальной CI-матрице) либо создавать примитивы лениво внутри
async-контекста.

### P2-6. Устаревшие paginated-страницы никогда не удаляются

- `generator_output.py:44-47`: cleanup сохраняет все `modules/page-*.md` и `configs/page-*.md`
  по glob'у. Если число страниц уменьшилось (или пагинация исчезла), старые `page-N.md`
  остаются навсегда и продолжают попадать в `_index.json` (через `existing_files`).

Предложение: держать только страницы текущей генерации: пересечение glob'а с
`docs_files`-ключами текущего прогона (для forced-перегенерации), а «хвост» удалять.

### P2-7. `ai-docs help` завершается ошибкой rc=2

- `cli.py:22`: `"help"` включён в `KNOWN_COMMANDS`, поэтому `_normalize_argv` не подставляет `gen`,
  но subparser'а `help` нет → argparse печатает «invalid choice: 'help'» и выходит с rc=2
  (подтверждено исполнением).

Предложение: либо убрать `"help"` из `KNOWN_COMMANDS`, либо маппить его на `--help` (rc=0). Тест на rc.

## Проблемы P3

### P3-1. Дублирование названий доменов в mkdocs nav

`mkdocs.py:51-58` содержит локальную карту заголовков, дублирующую `DOMAIN_TITLES`,
и в ней нет `observability`/`service_mesh`/`data_storage` — в навигации появятся сырые ключи
(«service_mesh» вместо «Service Mesh / Ingress»). Использовать `DOMAIN_TITLES` напрямую.

### P3-2. Точки в именах каталогов калечатся в путях модулей

`generator_shared.py:41`: `.replace(".", "__")` применяется ко всему пути — `src/v1.2/mod.py`
→ `modules/src/v1__2/mod__py.md` (подтверждено). `mkdocs.py:120-127` восстанавливает `.`
только в последнем сегменте → в nav каталог отображается как `v1__2`. Консистентно, но
предлагается заменять точку только в имени файла.

### P3-3. `watch` игнорирует изменения в `.github/**`

`cli_watch.py:173`: фильтр скрытых каталогов (`p.startswith(".")`) отбрасывает события
в `.github/workflows/*` — при этом скан их включает (fix аудита №1). Несогласованность:
изменение CI-файла не запускает регенерацию. Добавить `.github` в исключения фильтра скрытых.

### P3-4. `llm_cache.json` растёт неограниченно

Ключи от старых версий файлов никогда не вымываются (`cache.py:28-29` сохраняет всё).
На долгоживущем репозитории файл монотонно растёт и целиком грузится в память.
Предложение: eviction по возрасту/размеру или пересборка кэша по ключам последнего прогона.

### P3-5. `_postprocess_mermaid_html` правит весь HTML-файл

`generator_output.py:127-131`: `data.replace(b"&gt;", b">")` применяется ко всему файлу,
если в нём есть хоть один mermaid-блок. Сейчас это безвредно (символ `>` легален в тексте HTML),
но правка вне целевых блоков — хрупкий приём: ограничить замену содержимым `<div class="mermaid">…</div>`.

### P3-6. Повторное чтение конфигурации и файлов

- `config.py:48-58`: `.ai-docs.yaml` перечитывается на каждый вызов `load_extension_config` /
  `load_prompt_overrides` / `load_source_url`; `scanner.py:196-209` (`path_in_scan_scope`)
  перечитывает YAML и `.gitignore` на каждый удалённый путь в `pr-diff`.
- `scanner.py:121-123`: файл читается дважды (`is_binary_file` + `read_bytes`).

Предложение: кэшировать разобранный конфиг по mtime либо передавать сверху; в
`path_in_scan_scope` — прекомпилировать спеки один раз на прогон.

### P3-7. Мелкие смеллы кода

- `generator_sections.py:130-473`: `build_sections` — god function на ~340 строк,
  возвращает кортеж из 8 элементов; каждая секция (overview/index/domains/modules/configs/changes)
  обрабатывается отдельной ad-hoc веткой.
- `changes_summary_holder: Dict[str, str]` (`generator_sections.py:414`) — словарь вместо переменной/Future.
- `_close_llm` продублирован в `cli.py`, `cli_prdiff.py`, `cli_watch.py`; блок «scan → config →
  output_root → from_env → generate_docs» почти идентичен в `_run_gen`/`_regen`/`run_prdiff` (~40 строк ×3).
- `generator_output.py:149`: `__serialize_index` с name-mangling двойным подчёркиванием.
- `import time` внутри функций (`generator_cache.py:157,175`, `mkdocs.py:169`).
- print-логирование без уровней/квота (нет `--verbose`/`--quiet` кроме lint) — рассмотреть `logging`.
- `llm.py:126-127`: ветка `for..else` недостижима (внутри цикла всегда `break`/`raise`) — мёртвый код.
- `summary.py:139`: `max_tokens=1800` захардкожен — не связан с `context_limit`/`input_budget`.
- `cli_watch.py:1-7`: docstring обещает «Scan once at startup, persist baseline» — не реализовано.
- `tokenizer.py:15-23`: молчаливый fallback на `_ByteEncoding` (1 токен = 1 байт) при недоступности
  tiktoken-энкодинга (например, offline) — по политике проекта fallback должен логироваться.
- Mermaid-диаграмма валидируется только промптом (`generator_sections.py:30-38`) — нет
  post-проверки синтаксиса; сломанная диаграмма попадёт на сайт.

## Архитектурные предложения

### A. Довести library-first до конца (низкий риск, высокая отдача)

Аудит №1 ввёл `GenerationConfig` и `generate_docs_async`, но остались стыки:

1. Единый CLI-bootstrap: выделить `RunContext` (scan → config → output_root → LLMClient),
   используемый `gen`/`watch`/`pr-diff` — убирает тройное дублирование и расхождения
   (например, `write_readme_flag` в watch и gen вычисляются одинаково, но в двух местах).
2. Убрать дублирующие параметры `generate_docs(..., prompt_store=, source_url=, force_sections=,
   regen_all_threshold=)` — оставить только `generation_config` (сейчас два способа задать одно и то же).
3. Типизировать LLM-границу: `class LLMProtocol(Protocol): async def chat(...)`, вместо
   нетипизированного `llm` во всех сигнатурах.
4. Удалить legacy-глобали `prompts._active_store`/`site_config._source_url` после проверки,
   что внешних вызовов нет (сейчас pipeline их не использует).

### B. Декларативная модель секций вместо ad-hoc веток

Сейчас каждая секция в `build_sections` — уникальный код (overview читается с диска,
testing рендерится синхронно, modules пагинируется inline-функцией, changes — через holder-словарь).
Предложение: описать секции таблицей `SectionSpec(key, title, out_path, context_builder,
renderer, forced_tokens)` и один общий исполнитель: планирование (что перегенерировать) →
построение контекстов → рендер → запись. Это разрезает god function, делает `is_forced`-токены
единообразными и упрощает добавление секций. Cleanup в `write_docs` тогда строится из тех же
spec'ов, а не из повторённого списка keep-путей (сейчас списки секций перечислены минимум
в трёх местах: SECTION_TITLES, keep_files, mkdocs nav).

### C. Валидация на LLM-границе

Единая точка пост-обработки ответа: непустой `content`, проверка `finish_reason`,
опциональная схема (теги `<overview_summary>`/`<module_summary>` уже есть — сейчас их отсутствие
даёт пустые строки без сигнала: `_extract_tagged_block` возвращает `""`, и это молча становится
пустым summary). Ошибка формата → повтор с уточнением или явный fail, но не пустой артефакт.

### D. Правила доменов: сегменты вместо подстрок

`detect_domains` перевести на сопоставление сегментов пути и якорные позиции
(`parts[-2] == "tasks"` только при наличии соседних ansible-маркеров, `s3`/`redis` — только
для config/infra-расширений). Плюс инвариант: файл с кодовым расширением не теряет `type="code"`
(см. P1-2). Это отдельный модуль правил уже есть (`domain_rules.py`) — менять только матчинг.

### E. Наблюдаемость

Заменить `print` на `logging` с уровнями (`INFO` — прогресс, `WARNING` — fallback'и/insecure,
`DEBUG` — diff-детали), флаг `--verbose/--quiet` в CLI. Это же закроет требование политики
«fallback разрешён только с логированием».

## Рекомендуемый порядок работ

1. **P1-волна (корректность):** P1-1 (IndexError), P1-5 (кэш None/finish_reason),
   P1-4 (GenerationError для секций), P1-3 (watch self-trigger), P1-2 (домены/type).
   Проверка: юнит-тесты на каждый пункт + `pytest -q`.
2. **P2-волна (поведение CLI/ресурсы):** P2-1 (dependencies.md), P2-2 (--exclude),
   P2-3 (lint URL), P2-7 (help), P2-6 (page-N.md), P2-4 (tokenizer memory), P2-5 (requires-python).
3. **Рефакторинг:** предложения A (bootstrap + config) и B (SectionSpec) — по отдельности,
   с сохранением публичного CLI-контракта; затем C/D/E.

## Минимальные тесты для первого PR

- `_needs_doxygen_fix("5")` не бросает исключение; `_needs_doxygen_fix("1. пункт")` → True.
- `app/tasks/worker.py` классифицируется как `code` и получает module summary.
- Событие watchdog по `mkdocs.yml`/`README.md` не вызывает регенерацию.
- Fake LLM с ошибкой в `generate_section` → `GenerationError`, rc=1 (без traceback).
- Ответ LLM с `content=None` → понятная ошибка, ключ в `llm_cache.json` не появляется.
- Два прогона `gen` подряд без изменений не модифицируют LLM-часть `dependencies.md`.
- `scan_source(exclude={"*.log"})` не включает `mkdocs.yml`.
- `ai-docs lint --source https://...` → rc=2 без клонирования.
- `ai-docs help` → rc=0 и текст справки.
