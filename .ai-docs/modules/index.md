# Модули

```markdown
# Модули

## scan

Модуль `scan` отвечает за рекурсивное сканирование исходных кодов из локальной директории или удалённого Git-репозитория. Поддерживает фильтрацию файлов по шаблонам, обработку `.gitignore`, определение типов файлов и исключение бинарных или слишком больших файлов.

### Класс `ScanResult`

Результат сканирования исходного кода. Содержит список проанализированных файлов и метаданные.

#### Поля
- `root` — абсолютный путь к корневой директории сканирования.
- `files` — список словарей с информацией о каждом файле: путь, размер, содержимое, тип, домены.
- `source` — исходный URL или путь, переданный на вход.
- `repo_name` — имя репозитория (из URL или имени директории).

#### Методы
- `_load_ignore_specs(root: Path) -> List[pathspec.PathSpec]`  
  Загружает и компилирует правила игнорирования из `.gitignore` и `.build_ignore`.  
  Возвращает список скомпилированных `PathSpec` для сопоставления с путями.

- `_should_include(rel_path: str, include: Optional[List], exclude: Optional[List], ignore_specs: List[PathSpec]) -> bool`  
  Проверяет, должен ли файл быть включён в результаты. Учитывает пользовательские шаблоны и ignore-файлы.

- `_scan_directory(root: Path, include: List, exclude: List, max_size: int) -> List[Dict]`  
  Рекурсивно сканирует директорию. Возвращает список словарей с метаданными и содержимым включённых файлов.

- `_clone_repo(repo_url: str) -> Tuple[Path, str]`  
  Клонирует Git-репозиторий в временный каталог.  
  **Исключения**: `RuntimeError`, если клонирование не удалось.

- `scan_source(source: str, include: List = DEFAULT_INCLUDE_PATTERNS, exclude: List = DEFAULT_EXCLUDE_PATTERNS, max_size: int = 200000) -> ScanResult`  
  Основной метод: запускает сканирование по локальному пути или URL.  
  **Исключения**: `FileNotFoundError` (если путь не существует), `RuntimeError` (ошибка клонирования).

---

## cli

Модуль `cli` реализует интерфейс командной строки для генерации документации.

### Функции
- `parse_args() -> argparse.Namespace`  
  Парсит аргументы командной строки.  
  Поддерживает: `--source`, `--output`, `--readme`, `--mkdocs`, `--language`, `--include`, `--exclude`, `--max-size`, `--cache-dir`, `--no-cache`, `--threads`, `--local-site`, `--force`.  
  **Исключения**: может вызвать `SystemExit` при ошибке парсинга.

- `resolve_output(source: str, output: Optional[str], repo_name: str) -> Path`  
  Определяет итоговую директорию вывода. Если `output` не задан, формирует путь по умолчанию.

- `main() -> None`  
  Основная точка входа: парсит аргументы, сканирует исходники, инициализирует LLM и запускает генерацию.  
  **Исключения**: возможны при ошибках сканирования, доступа к LLM или записи файлов.

---

## llm

Модуль `llm` предоставляет клиент для взаимодействия с LLM через HTTP API с поддержкой кэширования.

### Класс `LLMClient`

Клиент для отправки запросов к языковой модели.

#### Поля
- `api_key` — ключ аутентификации.
- `base_url` — базовый URL API (например, `https://api.openai.com/v1`).
- `model` — идентификатор модели (например, `gpt-4o-mini`).
- `temperature` — параметр случайности генерации (по умолчанию `0.2`).
- `max_tokens` — макс. количество токенов в ответе.
- `context_limit` — общий лимит токенов в контексте.

#### Методы
- `__init__(api_key, base_url, model, temperature=0.2, max_tokens=1200, context_limit=8192)`  
  Инициализирует клиент.
- `_cache_key(payload: Dict) -> str`  
  Генерирует хеш-ключ для кэширования на основе нормализованного JSON.
- `chat(messages: List[Dict], cache: Optional[Dict] = None) -> str`  
  Отправляет чат-запрос к API и возвращает ответ модели.

### Функция
- `from_env() -> LLMClient`  
  Создаёт клиент на основе переменных окружения.  
  **Исключения**: `RuntimeError`, если `OPENAI_API_KEY` не задан.

---

## docs

Модуль `docs` отвечает за генерацию и обработку документации по исходным файлам с использованием LLM.

### Ключевые функции
- `summarize_file(content: str, file_type: str, domains: List[str], llm, llm_cache: Dict, model: str, detailed: bool = False) -> str`  
  Генерирует краткое или детальное резюме файла. Поддерживает Doxygen-стиль при `detailed=True`.

- `_normalize_module_summary(summary: str, llm, llm_cache: Dict) -> str`  
  Приводит резюме к строгому Doxygen-формату.

- `write_summary(summary_dir: Path, rel_path: str, summary: str) -> Path`  
  Сохраняет резюме в Markdown-файл, сохраняя структуру путей.

- `generate_docs(files: List[Dict], output_root: Path, cache_dir: Path, llm: LLMClient, language: str, write_readme: bool, write_mkdocs: bool, use_cache: bool = True, threads: int = 1, local_site: bool = False, force: bool = False) -> None`  
  Основная функция: генерирует документацию, суммаризует файлы, создаёт README и/или `mkdocs.yml`. Поддерживает многопоточность.

- `_is_test_path(path: str) -> bool`  
  Определяет, является ли путь тестовым (по имени папки/файла).

- `_collect_dependencies(files: Dict[str, Dict]) -> List[str]`  
  Извлекает зависимости из `pyproject.toml`, `requirements.txt`, `package.json`.

- `_generate_section(llm, llm_cache, title, context, language) -> str`  
  Генерирует раздел документации (например, "Архитектура") с Mermaid-диаграммой.

- `_strip_duplicate_heading(content: str, title: str) -> str`  
  Удаляет дублирующий заголовок из сгенерированного текста.

- `_generate_readme(llm, llm_cache, project_name, overview_context, language) -> str`  
  Генерирует содержимое `README.md`.

- `_truncate_context(context: str, model: str, max_tokens: int) -> str`  
  Обрезает контекст до указанного количества токенов.

- `format_changes_md(added, modified, deleted, regenerated, summary) -> str`  
  Формирует Markdown-отчёт о изменениях в файлах и секциях.

---

## mkdocs

Модуль `mkdocs` генерирует конфигурацию `mkdocs.yml` и записывает файлы документации.

### Функции
- `build_mkdocs_yaml(site_name: str, sections: Dict, configs: Dict, local_site: bool = False, has_modules: bool = False, module_nav_paths: List[str] | None = None) -> str`  
  Генерирует YAML-конфигурацию для MkDocs.

- `_build_modules_nav(module_paths: List[str]) -> List[Dict]`  
  Строит иерархическую навигацию по модулям.

- `_insert_nav_node(tree: Dict, parts: List[str], rel_path: str) -> None`  
  Рекурсивно вставляет узел в дерево навигации.

- `_tree_to_nav(tree: Dict) -> List[Dict]`  
  Преобразует дерево навигации в список для MkDocs.

- `write_docs_files(docs_dir: Path, files: Dict[str, str]) -> None`  
  Записывает все файлы документации на диск.

---

## utils

Модуль `utils` предоставляет вспомогательные функции для работы с файлами, путями и хешированием.

### Функции
- `sha256_bytes(data: bytes) -> str` — возвращает SHA-256 хеш в hex.
- `sha256_text(text: str) -> str` — хеширует текстовую строку.
- `read_text_file(path: Path) -> str` — читает файл в UTF-8, игнорируя ошибки.
- `safe_slug(path: str) -> str` — преобразует строку в безопасный слаг.
- `ensure_dir(path: Path) -> None` — создаёт директорию и родителей.
- `is_binary_file(path: Path, sample_size: int = 2048) -> bool` — определяет, бинарный ли файл.
- `is_url(value: str) -> bool` — проверяет, является ли строка URL.
- `to_posix(path: Path) -> str` — преобразует путь в POSIX-формат.

---

## classify

Модуль `classify` определяет тип файла и его домены (инфраструктура, CI, Docker и т.д.).

### Функции
- `classify_type(path: Path) -> str`  
  Возвращает тип файла: `code`, `docs`, `config`, `data`, `infra`, `ci`, `other`.

- `detect_domains(path: Path, content_snippet: str) -> Set[str]`  
  Определяет домены по имени, пути и фрагменту содержимого (например, `kubernetes`, `docker`).

- `is_infra(domains: Set[str]) -> bool`  
  Проверяет, относится ли файл к инфраструктурным доменам.

---

## cache

Модуль `cache` управляет кэшем файлов и ответов LLM.

### Класс `CacheManager`

#### Поля
- `cache_dir` — директория хранения кэша.
- `index_path` — путь к `index.json`.
- `llm_cache_path` — путь к `llm_cache.json`.

#### Методы
- `__init__(cache_dir: Path)` — инициализирует менеджер и создаёт директорию.
- `load_index() -> Dict` — загружает индекс или возвращает пустой.
- `save_index(data: Dict) -> None` — сохраняет индекс.
- `load_llm_cache() -> Dict[str, str]` — загружает кэш LLM.
- `save_llm_cache(data: Dict[str, str]) -> None` — сохраняет кэш LLM.
- `diff_files(current_files: Dict[str, Dict]) -> Tuple[added, modified, deleted, unchanged]`  
  Сравнивает текущие файлы с предыдущим состоянием.

---

## tokens

Модуль `tokens` отвечает за подсчёт и разбиение текста на токены.

### Функции
- `get_encoding(model: str)`  
  Возвращает кодировку `tiktoken` для модели, fallback к `cl100k_base`.

- `count_tokens(text: str, model: str) -> int`  
  Возвращает количество токенов в тексте.

- `chunk_text(text: str, model: str, max_tokens: int) -> List[str]`  
  Разбивает текст на фрагменты по лимиту токенов.

---

## __main__

Модуль `__main__` обеспечивает запуск приложения как скрипта: `python -m ai_docs`.

### Функции
- `_load_main()`  
  Динамически загружает `main` из `ai_docs.cli`.  
  **Исключения**: `ImportError` — обрабатывается через fallback.

- `main()`  
  Точка входа при запуске модуля. Вызывает `main()` из `cli`.
```

## Список модулей

- [modules/ai_docs/__init__](ai_docs/__init__.md)
- [modules/ai_docs/__main__](ai_docs/__main__.md)
- [modules/ai_docs/cache](ai_docs/cache.md)
- [modules/ai_docs/changes](ai_docs/changes.md)
- [modules/ai_docs/cli](ai_docs/cli.md)
- [modules/ai_docs/domain](ai_docs/domain.md)
- [modules/ai_docs/generator](ai_docs/generator.md)
- [modules/ai_docs/llm](ai_docs/llm.md)
- [modules/ai_docs/mkdocs](ai_docs/mkdocs.md)
- [modules/ai_docs/scanner](ai_docs/scanner.md)
- [modules/ai_docs/summary](ai_docs/summary.md)
- [modules/ai_docs/tokenizer](ai_docs/tokenizer.md)
- [modules/ai_docs/utils](ai_docs/utils.md)
