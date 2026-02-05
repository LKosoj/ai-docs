# Модули

Модули системы отвечают за сканирование кодовой базы, генерацию аннотаций, управление кэшем, построение документации и её финальную сборку. Все операции выполняются асинхронно с поддержкой параллелизма и кэширования для повышения производительности.

## Сканирование файлов

Модуль `scan` отвечает за рекурсивный анализ файловой системы или удалённого Git-репозитория. Поддерживает фильтрацию по шаблонам включения/исключения, игнорирование бинарных и крупных файлов, а также загрузку конфигурации из `.ai-docs.yaml`.

### Ключевые функции

- `scan_source(source: str, include: Set[str], exclude: Set[str], max_size: int) -> ScanResult` — основная точка входа для сканирования. Принимает путь или URL, возвращает `ScanResult`.
- `_load_extension_config(root: Path) -> Dict` — загружает пользовательские настройки расширений и правил исключения.
- `_should_include(rel_path: str, include, exclude, ignore_specs) -> bool` — проверяет, должен ли файл быть включён в результат.

### Структуры данных

```python
class ScanResult:
    root: Path
    files: List[Dict]  # Каждый словарь содержит: path, content, type, domains, size
    source: str
    repo_name: str
```

## Генерация аннотаций

Модуль предоставляет асинхронные функции для параллельной генерации сводок по файлам. Поддерживается обработка разных типов: код, конфигурации, модули.

### Основные функции

- `summarize_changed_files(...)`, `summarize_changed_modules(...)`, `summarize_changed_configs(...)` — генерируют аннотации для изменённых файлов.
- `summarize_missing(...)`, `summarize_missing_modules(...)`, `summarize_missing_configs(...)` — восстанавливают отсутствующие сводки.
- `run_one(path: str, meta: dict)` — обрабатывает один конфигурационный файл.

### Аргументы

- `to_summarize`: `List[Tuple[str, Dict]]` — список файлов и их метаданных.
- `summaries_dir`: `Path` — директория для сохранения аннотаций.
- `llm`: модель для генерации текста.
- `llm_cache`: `Dict[str, str]` — кэш ответов LLM.
- `threads`: `int` — максимальное число параллельных задач.
- `save_cb`: коллбэк после успешной обработки файла.
- `errors`: `List[str]` — накопление ошибок.

## Управление кэшем

Модуль `cache` обеспечивает сохранение и восстановление состояния между запусками. Использует `CacheManager` для работы с `index.json` и `llm_cache.json`.

### Класс `CacheManager`

```python
class CacheManager:
    def __init__(self, cache_dir: Path)
    def load_index(self) -> Dict
    def save_index(self, data: Dict) -> None
    def load_llm_cache(self) -> Dict[str, str]
    def save_llm_cache(self, data: Dict[str, str]) -> None
    def diff_files(self, current_files: Dict[str, Dict]) -> Tuple[added, modified, deleted, unchanged]
```

### Вспомогательные функции

- `init_cache(cache_dir, use_cache)`: инициализирует кэш, возвращает `(cache, llm_cache, index_data, prev_files)`.
- `build_file_map(files)`: строит карту файлов с хэшами.
- `diff_files(cache, file_map)`: сравнивает текущее и предыдущее состояние.
- `cleanup_orphan_summaries(...)`: удаляет "затерянные" аннотации.

## Генерация документации

Модуль `generate` строит иерархический контекст, генерирует разделы и формирует финальный README. Поддерживает принудительную перегенерацию отдельных секций.

### Ключевые функции

- `build_sections(...) -> Tuple`: основная логика построения документации.
- `generate_section(...) -> str`: генерирует один раздел.
- `generate_readme(...) -> str`: формирует README.md.
- `build_hierarchical_context(...) -> str`: рекурсивно сжимает контекст до лимита токенов.

### Параметры

- `file_map`: карта всех файлов проекта.
- `llm`, `llm_cache`: модель и кэш.
- `language`: язык документации.
- `force_sections`: `Set[str]` — секции, требующие перегенерации.

## Сборка документации

Модуль `build` отвечает за запись файлов, генерацию `mkdocs.yml`, интеграцию с Mermaid.js и постобработку HTML.

### Основные функции

- `write_docs(...)`: записывает документацию, удаляет устаревшие файлы.
- `build_mkdocs(...)`: генерирует конфигурацию MkDocs и собирает сайт.
- `_postprocess_mermaid_html(...)`: исправляет escape-последовательности в диаграммах.
- `write_readme(...)`: обновляет `README.md`.

### Вспомогательные

- `build_mkdocs_yaml(...) -> str`: генерирует YAML-конфиг.
- `_build_tree_nav(...) -> List[Dict]`: строит иерархию навигации.
- `__serialize_index(...) -> str`: сериализует индекс с метаданными.

## LLM-клиент

Модуль `llm_client` предоставляет асинхронный интерфейс для работы с OpenAI-совместимыми API.

### Класс `LLMClient`

```python
class LLMClient:
    def __init__(api_key, base_url, model, temperature, max_tokens, context_limit)
    def chat(messages: List[Dict], cache: Dict) -> str
    def _compute_read_timeout(input_tokens) -> float
    def _cache_key(payload) -> str
```

- Поддерживает кэширование, адаптивный таймаут, повторные попытки.
- `from_env() -> LLMClient`: создаёт клиент из переменных окружения.

## Утилиты

Модуль `utils` включает вспомогательные функции для работы с файлами, путями и данными.

### Основные функции

- `sha256_text(text) -> str`, `sha256_bytes(data) -> str`: хеширование.
- `read_text_file(path) -> str`: безопасное чтение файла.
- `ensure_dir(path)`: создание директории с родителями.
- `is_binary_file(path) -> bool`: проверка на бинарный файл.
- `to_posix(path) -> str`: преобразование пути в POSIX-формат.
- `is_url(value) -> bool`: проверка строки на URL.

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
