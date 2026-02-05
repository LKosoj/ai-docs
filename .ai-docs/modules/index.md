# Модули

Модули системы отвечают за автоматизированную генерацию, обновление и управление технической документацией на основе анализа исходного кода, конфигураций и взаимодействия с LLM. Архитектура модульная, обеспечивает асинхронную обработку, кэширование, контроль параллелизма и устойчивость к ошибкам.

## Генерация аннотаций

Модуль предоставляет асинхронные функции для генерации аннотаций к файлам, модулям и конфигурациям. Поддерживает семафоры для ограничения одновременных запросов к LLM, кэширование, прогресс-логирование и накопление ошибок без прерывания выполнения.

### Ключевые структуры данных
- `Tuple[str, Dict]` — Пара: путь к файлу и его метаданные.
- `List[str]` — Список для накопления сообщений об ошибках.

### Функции

#### `summarize_changed_files`
```python
async def summarize_changed_files(
    to_summarize: List[Tuple[str, Dict]],
    summaries_dir: Path,
    llm,
    llm_cache: Dict[str, str],
    threads: int,
    save_cb,
    errors: List[str]
) -> None
```
Генерирует аннотации для изменённых файлов и сохраняет в указанный каталог.  
**Аргументы:**
- `to_summarize` — Список пар (путь, метаданные) для аннотирования.
- `summaries_dir` — Каталог сохранения аннотаций.
- `llm` — Языковая модель.
- `llm_cache` — Кэш ответов LLM.
- `threads` — Макс. число одновременных запросов.
- `save_cb` — Коллбэк после успешной обработки.
- `errors` — Список для ошибок.  
**Исключения:** Ошибки добавляются в `errors`, выполнение продолжается.

#### `summarize_changed_modules`
Аналогично `summarize_changed_files`, но для модулей (код без тестов). Сохраняет в `module_summaries_dir`.

#### `summarize_changed_configs`
Аналогично, но для конфигурационных файлов. Сохраняет в `config_summaries_dir`.

#### `summarize_missing`, `summarize_missing_modules`, `summarize_missing_configs`
Асинхронно восстанавливают отсутствующие аннотации для файлов, модулей и конфигов соответственно. Отличаются только входными списками и каталогами сохранения. Все отображают прогресс обработки.

---

## Сканирование файловой системы

Модуль отвечает за сканирование локальных директорий или Git-репозиториев с фильтрацией по расширениям, размеру и правилам игнорирования (`.gitignore`, `.build_ignore`).

### Ключевая структура
#### `ScanResult`
Результат сканирования.
- `root`: `Path` — Корневой путь.
- `files`: `List[Dict]` — Список файлов с метаданными (путь, тип, содержимое, домены).
- `source`: `str` — Источник (путь или URL).
- `repo_name`: `str` — Имя репозитория.

### Основные функции

#### `scan_source`
```python
def scan_source(
    source: str,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
    max_size: int = 200_000
) -> ScanResult
```
Сканирует локальную директорию или Git-репозиторий.  
**Аргументы:**
- `source` — Путь или URL.
- `include` — Паттерны включения (glob).
- `exclude` — Паттерны исключения.
- `max_size` — Макс. размер файла в байтах.  
**Возвращает:** `ScanResult`.  
**Исключения:** `FileNotFoundError`, если путь не существует.

#### Вспомогательные функции
- `_load_extension_config` — Загружает `.ai-docs.yaml` с настройками расширений.
- `_build_default_include_patterns` — Формирует glob-паттерны по расширениям.
- `_load_ignore_specs` — Загружает правила из `.gitignore` и `.build_ignore`.
- `_should_include` — Проверяет, должен ли файл быть включён.
- `_scan_directory` — Рекурсивно сканирует директорию.
- `_clone_repo` — Клонирует Git-репозиторий во временную папку.

---

## Управление документацией

Модуль координирует запись файлов документации, генерацию `mkdocs.yml`, интеграцию с Mermaid.js и постобработку HTML.

### Ключевые структуры
- `docs_files`: `Dict[str, str]` — Путь → содержимое.
- `file_map`: `Dict[str, Dict]` — Карта исходных файлов.
- `module_pages`, `config_pages`: `Dict[str, str]` — Пути к страницам документации.
- `configs_written`: `Dict[str, str]` — Записанные конфиги для `mkdocs.yml`.

### Функции

#### `write_docs`
```python
def write_docs(
    output_root: Path,
    docs_dir: Path,
    docs_files: Dict[str, str],
    file_map: Dict[str, Dict],
    module_pages: Dict[str, str],
    config_pages: Dict[str, str],
    has_changes: bool
) -> None
```
Записывает документацию, обновляет индекс, добавляет ассеты, очищает устаревшие файлы.

#### `write_readme`
```python
def write_readme(output_root: Path, readme: str, force: bool) -> None
```
Записывает `README.md` в корень. Перезаписывает, если `force=True`.

#### `build_mkdocs`
```python
def build_mkdocs(
    output_root: Path,
    module_nav_paths: List[str],
    config_nav_paths: List[str],
    configs_written: Dict[str, str],
    write_mkdocs: bool,
    local_site: bool
) -> None
```
Генерирует `mkdocs.yml` и собирает сайт.  
**Исключения:** `RuntimeError`, если `mkdocs` не установлен.

#### `_postprocess_mermaid_html`
Исправляет `&gt;` на `>` в Mermaid-блоках HTML для корректного отображения.

#### `__serialize_index`
Сериализует индекс документации в JSON с временной меткой и метаинформацией.

---

## Генерация документации

Модуль строит контекст, генерирует разделы (архитектура, тестирование, README) и управляет кэшированием.

### Ключевые структуры
- `file_map`: `Dict[str, Dict]` — Метаданные файлов.
- `llm_cache`: `Dict[str, str]` — Кэш LLM.
- `DOMAIN_TITLES`: `Dict[str, str]` — Сопоставление доменов и заголовков.

### Функции

#### `generate_section`
```python
async def generate_section(
    llm,
    llm_cache: Dict[str, str],
    title: str,
    context: str,
    language: str
) -> str
```
Генерирует текст раздела по контексту.

#### `generate_readme`
```python
async def generate_readme(
    llm,
    llm_cache: Dict[str, str],
    project_name: str,
    overview_context: str,
    language: str
) -> str
```
Формирует `README.md` с обзором, архитектурой, быстрым стартом.

#### `build_hierarchical_context`
Строит иерархический контекст из резюме файлов с учётом лимита токенов.

#### `build_sections`
Основная функция генерации всех разделов. Возвращает контексты, тесты, зависимости, обобщённый контекст.

#### Вспомогательные
- `truncate_context` — Обрезает текст по лимиту токенов.
- `summarize_chunk` — Сжимает фрагмент текста.
- `render_testing_section` — Формирует раздел тестирования.
- `format_changes_md` — Форматирует сводку изменений в Markdown.
- `collect_dependencies` — Собирает зависимости из `requirements.txt`, `pyproject.toml`, `package.json`.
- `render_project_configs_index` — Генерирует оглавление конфигов.

---

## CLI и точка входа

Модуль обрабатывает аргументы командной строки и запускает процесс генерации.

### Функции

#### `parse_args`
Парсит аргументы:
- `--source`, `--output`, `--language`, `--include`, `--exclude`, `--max-size`
- `--readme`, `--mkdocs`, `--local-site`, `--force`
- `--threads`, `--cache-dir`, `--no-cache`, `--regen`

#### `resolve_output`
Определяет путь вывода на основе `source`, `output` и `repo_name`.

#### `main`
Основная точка входа. Загружает конфиг, сканирует, инициализирует LLM, запускает генерацию.

---

## LLM-клиент

Асинхронный клиент для работы с OpenAI-совместимыми API.

### Класс `LLMClient`
**Поля:**
- `api_key`, `base_url`, `model`, `temperature`, `max_tokens`, `context_limit`
- `_cache_lock`, `_client` — Экземпляр `AsyncOpenAI`

**Методы:**
- `__init__` — Инициализация с параметрами модели.
- `_estimate_input_tokens` — Оценка токенов во входных сообщениях.
- `_compute_read_timeout` — Адаптивный таймаут по количеству токенов.
- `_cache_key` — Генерация хеша запроса.
- `chat` — Отправка запроса к LLM с кэшированием.
- `from_env` — Создание клиента из переменных окружения.  
**Исключения:** `RuntimeError`, если `OPENAI_API_KEY` не задан.

---

## Нормализация и обработка текста

Модуль нормализует сгенерированные описания под нужный формат (Doxygen, универсальный).

### Функции

#### `_normalize_module_summary`
Приводит описание модуля к Doxygen-формату.

#### `_normalize_config_summary`
Нормализует описание конфига к универсальному стилю.

#### `_format_config_blocks`
Форматирует конфигурационные блоки, разделяя `<br>`.

#### `_strip_fenced_markdown`
Удаляет ```markdown из текста.

#### `summarize_file`
Генерирует резюме файла с учётом типа и доменов.

#### `write_summary`
Сохраняет резюме в файл Markdown в `summary_dir`.

---

## Управление кэшем

Модуль обеспечивает загрузку, сохранение и синхронизацию кэша между запусками.

### Класс `CacheManager`
**Поля:**
- `cache_dir`, `index_path`, `llm_cache_path`

**Методы:**
- `__init__` — Создаёт директории и файлы кэша.
- `load_index`, `save_index` — Работа с `index.json`.
- `load_llm_cache`, `save_llm_cache` — Работа с `llm_cache.json` (с резервным копированием при повреждении).
- `diff_files` — Сравнивает текущие файлы с кэшем, возвращает `added`, `changed`, `deleted`, `unchanged`.

### Вспомогательные функции
- `init_cache` — Инициализирует кэш и загружает данные.
- `build_file_map` — Строит карту файлов с хешами.
- `diff_files` — Вычисляет различия с кэшем.
- `ensure_summary_dirs` — Создаёт директории для сводок.
- `save_cache_snapshot` — Сохраняет снимок состояния.
- `carry_unchanged_summaries` — Переносит сводки для неизменённых файлов.
- `cleanup_orphan_summaries`, `cleanup_deleted_summaries` — Удаляют устаревшие сводки.

## Список модулей

- [modules/ai_docs/__init____py](ai_docs/__init____py.md)
- [modules/ai_docs/__main____py](ai_docs/__main____py.md)
- [modules/ai_docs/cache__py](ai_docs/cache__py.md)
- [modules/ai_docs/changes__py](ai_docs/changes__py.md)
- [modules/ai_docs/cli__py](ai_docs/cli__py.md)
- [modules/ai_docs/domain__py](ai_docs/domain__py.md)
- [modules/ai_docs/generator__py](ai_docs/generator__py.md)
- [modules/ai_docs/generator_cache__py](ai_docs/generator_cache__py.md)
- [modules/ai_docs/generator_output__py](ai_docs/generator_output__py.md)
- [modules/ai_docs/generator_sections__py](ai_docs/generator_sections__py.md)
- [modules/ai_docs/generator_shared__py](ai_docs/generator_shared__py.md)
- [modules/ai_docs/generator_summarize__py](ai_docs/generator_summarize__py.md)
- [modules/ai_docs/llm__py](ai_docs/llm__py.md)
- [modules/ai_docs/mkdocs__py](ai_docs/mkdocs__py.md)
- [modules/ai_docs/scanner__py](ai_docs/scanner__py.md)
- [modules/ai_docs/summary__py](ai_docs/summary__py.md)
- [modules/ai_docs/tokenizer__py](ai_docs/tokenizer__py.md)
- [modules/ai_docs/utils__py](ai_docs/utils__py.md)
