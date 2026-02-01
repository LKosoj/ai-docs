# Модули

## scan

Модуль для сканирования исходных кодов из локальной директории или удалённого Git-репозитория. Поддерживает рекурсивный обход файловой системы с фильтрацией по шаблонам включения/исключения, обработку `.gitignore`, определение типов файлов и исключение бинарных или слишком больших файлов.

### Класс `ScanResult`

Результат сканирования исходного кода. Содержит список проанализированных файлов и метаданные.

#### Поля
- `root` — абсолютный путь к корневой директории сканирования.
- `files` — список словарей с информацией о каждом файле: путь, размер, содержимое, тип, домены.
- `source` — исходный URL или путь, переданный на вход.
- `repo_name` — имя репозитория (из URL или имени директории).

#### Методы

##### `_load_ignore_specs(root: Path) -> List[pathspec.PathSpec]`
Загружает и компилирует правила игнорирования из `.gitignore` и `.build_ignore` в указанной директории.

**Возвращает**  
Список скомпилированных `pathspec.PathSpec` для сопоставления с путями.

---

##### `_should_include(rel_path: str, include: Optional[List[str]], exclude: Optional[List[str]], ignore_specs: List[pathspec.PathSpec]) -> bool`
Проверяет, должен ли файл быть включён в результаты сканирования.

**Аргументы**
- `rel_path` — относительный путь к файлу (в формате POSIX).
- `include` — пользовательские шаблоны включения (если `None`, включаются все, кроме исключённых).
- `exclude` — пользовательские шаблоны исключения.
- `ignore_specs` — список скомпилированных спецификаций игнорирования.

**Возвращает**  
`True`, если файл должен быть включён; `False`, если пропущен.

---

##### `_scan_directory(root: Path, include: Optional[List[str]], exclude: Optional[List[str]], max_size: int) -> List[Dict]`
Рекурсивно сканирует директорию и возвращает список проанализированных файлов.

**Аргументы**
- `root` — корневая директория.
- `include` — шаблоны включения (glob).
- `exclude` — шаблоны исключения (glob).
- `max_size` — максимальный размер файла в байтах (файлы больше игнорируются).

**Возвращает**  
Список словарей с полями: `path`, `size`, `content`, `type`, `domains`.

---

##### `_clone_repo(repo_url: str) -> Tuple[Path, str]`
Клонирует Git-репозиторий в временный каталог.

**Аргументы**
- `repo_url` — URL репозитория (HTTP/HTTPS).

**Возвращает**  
Кортеж: `(путь_к_временной_директории, имя_репозитория)`.

**Исключения**  
- `RuntimeError` — если клонирование завершилось с ошибкой.

---

##### `scan_source(source: str, include: Optional[List[str]] = None, exclude: Optional[List[str]] = None, max_size: int = 200000) -> ScanResult`
Основной метод модуля. Запускает сканирование по локальному пути или URL.

**Аргументы**
- `source` — путь к директории или URL репозитория.
- `include` — шаблоны включения (по умолчанию: `DEFAULT_INCLUDE_PATTERNS`).
- `exclude` — шаблоны исключения (по умолчанию: `DEFAULT_EXCLUDE_PATTERNS`).
- `max_size` — максимальный размер файла (по умолчанию: 200 КБ).

**Возвращает**  
Объект `ScanResult`.

**Исключения**  
- `FileNotFoundError` — если локальный путь не существует.
- `RuntimeError` — если не удалось клонировать репозиторий.

---

## cli

Модуль командной строки для запуска генерации документации. Парсит аргументы, инициализирует компоненты и запускает основной процесс.

### Функции

##### `parse_args() -> argparse.Namespace`
Парсит аргументы командной строки.

**Аргументы**
- `--source` — путь или URL (обязательный).
- `--output` — директория вывода (по умолчанию: `./output/<repo>`).
- `--readme` — генерировать `README.md`.
- `--mkdocs` — генерировать `mkdocs.yml`.
- `--language` — язык (`ru` или `en`, по умолчанию: `ru`).
- `--include`, `--exclude` — шаблоны включения/исключения.
- `--max-size` — макс. размер файла (байт, по умолчанию: 200000).
- `--cache-dir` — директория кэша (по умолчанию: `.ai_docs_cache`).
- `--no-cache` — отключить кэширование LLM.
- `--threads` — количество потоков (по умолчанию: из окружения).
- `--local-site` — настройка MkDocs для локального запуска.
- `--force` — перезаписать существующий `README.md`.

**Возвращает**  
Объект `Namespace` с аргументами.

**Исключения**  
- `SystemExit` — при ошибке парсинга.

---

##### `resolve_output(source: str, output: Optional[str], repo_name: str) -> Path`
Определяет итоговую директорию вывода.

**Возвращает**  
Объект `Path` к выходной директории.

---

##### `main() -> None`
Основная точка входа. Выполняет:
1. Парсинг аргументов.
2. Сканирование исходников.
3. Инициализацию `LLMClient`.
4. Генерацию документации.

**Исключения**  
Может выбросить ошибки при сканировании, доступе к LLM или записи файлов.

---

## llm

Модуль для взаимодействия с LLM через HTTP API с поддержкой кэширования.

### Класс `LLMClient`

Клиент для отправки запросов к LLM.

#### Методы

##### `__init__(api_key: str, base_url: str, model: str, temperature: float = 0.2, max_tokens: int = 1200, context_limit: int = 8192)`
Инициализирует клиента.

**Аргументы**
- `api_key` — ключ аутентификации.
- `base_url` — базовый URL API (например, `https://api.openai.com/v1`).
- `model` — идентификатор модели.
- `temperature` — степень случайности (по умолчанию: 0.2).
- `max_tokens` — макс. токенов в ответе (по умолчанию: 1200).
- `context_limit` — общий лимит токенов (по умолчанию: 8192).

---

##### `_cache_key(payload: Dict) -> str`
Генерирует SHA-256 хеш от нормализованного JSON-представления запроса.

**Возвращает**  
Строку — ключ кэша.

---

##### `chat(messages: List[Dict], cache: Optional[Dict[str, str]] = None) -> str`
Отправляет чат-запрос к модели.

**Аргументы**
- `messages` — список сообщений: `{"role": "...", "content": "..."}`.
- `cache` — словарь кэша (ключ — хеш запроса, значение — ответ).

**Возвращает**  
Текст ответа от модели.

**Исключения**  
- `RuntimeError` — если ответ не содержит контента.
- `requests.HTTPError` — при HTTP-ошибке.
- `requests.Timeout` — при таймауте.

---

##### `from_env() -> LLMClient`
Создаёт клиент на основе переменных окружения.

**Требует**  
`OPENAI_API_KEY`.

**Исключения**  
- `RuntimeError` — если ключ не задан.

---

## docs

Модуль генерации документации по исходным файлам с использованием LLM.

### Функции

##### `summarize_file(content: str, file_type: str, domains: List[str], llm_client, llm_cache: Dict, model: str, detailed: bool = False) -> str`
Генерирует краткое или детальное резюме файла.

**Возвращает**  
Markdown или Doxygen-текст.

---

##### `_normalize_module_summary(summary: str, llm_client, llm_cache: Dict) -> str`
Нормализует текст резюме в строгий Doxygen-формат.

---

##### `write_summary(summary_dir: Path, rel_path: str, summary: str) -> Path`
Сохраняет резюме в `.md` файл.

**Возвращает**  
Путь к созданному файлу.

---

##### `build_mkdocs_yaml(site_name: str, sections: Dict, configs: Dict, local_site: bool = False, has_modules: bool = False, module_nav_paths: List[str] | None = None) -> str`
Генерирует содержимое `mkdocs.yml`.

**Возвращает**  
YAML-строку.

---

##### `_build_modules_nav(module_paths: List[str]) -> List[Dict]`
Строит иерархическую навигацию по модулям.

---

##### `_insert_nav_node(tree: Dict, parts: List[str], rel_path: str) -> None`
Рекурсивно вставляет узел в дерево навигации.

---

##### `_tree_to_nav(tree: Dict) -> List[Dict]`
Преобразует дерево в формат навигации MkDocs.

---

##### `write_docs_files(docs_dir: Path, files: Dict[str, str]) -> None`
Записывает документационные файлы в директорию.

**Исключения**  
Может выбросить `PermissionError` и др.

---

## generator

Модуль генерации полной документации проекта.

### Функции

##### `generate_docs(files: List[Dict], output_root: Path, cache_dir: Path, llm: LLMClient, language: str, write_readme: bool, write_mkdocs: bool, use_cache: bool = True, threads: int = 1)`
Генерирует:
- Разделы документации (архитектура, зависимости).
- Модули.
- `README.md`.
- `mkdocs.yml`.

**Аргументы**
- `files` — список файлов с метаданными.
- `output_root` — корень вывода.
- `cache_dir` — директория кэша.
- `llm` — клиент LLM.
- `language` — язык (`ru`, `en`).
- `write_readme`, `write_mkdocs` — флаги генерации.
- `use_cache` — использовать кэш.
- `threads` — количество потоков.

---

##### `_is_test_path(path: str) -> bool`
Проверяет, является ли путь тестовым (по имени папки/файла).

---

##### `_collect_dependencies(files: Dict[str, Dict]) -> List[str]`
Собирает зависимости из `requirements.txt`, `pyproject.toml`, `package.json`.

**Возвращает**  
Список строк: `"имя версия"`.

---

##### `_generate_section(llm: LLMClient, llm_cache: Dict, title: str, context: str, language: str) -> str`
Генерирует один раздел документации.

---

##### `_strip_duplicate_heading(content: str, title: str) -> str`
Удаляет дублирующий заголовок из текста.

---

##### `_generate_readme(...) -> str`
Генерирует `README.md` с обзором и инструкциями.

---

##### `_truncate_context(context: str, model: str, max_tokens: int) -> str`
Обрезает контекст до лимита токенов.

---

##### `_first_paragraph(text: str) -> str`
Извлекает первый абзац текста.

---

##### `_build_docs_index(...) -> Dict`
Формирует JSON-индекс документации с метаданными.

---

## utils

Вспомогательные функции для работы с файлами, путями и хешированием.

### Функции

##### `sha256_bytes(data: bytes) -> str`
Возвращает SHA-256 хеш от байтов.

---

##### `sha256_text(text: str) -> str`
Возвращает SHA-256 хеш от строки (в UTF-8).

---

##### `read_text_file(path: Path) -> str`
Читает файл в кодировке UTF-8, игнорируя ошибки.

---

##### `safe_slug(path: str) -> str`
Преобразует строку в безопасный слаг (только `a-z0-9_`).

---

##### `ensure_dir(path: Path) -> None`
Создаёт директорию и все родительские.

**Исключения**  
- `OSError` — при ошибке создания.

---

##### `is_binary_file(path: Path, sample_size: int = 2048) -> bool`
Определяет, является ли файл бинарным (по наличию нулевых байтов).

---

##### `is_url(value: str) -> bool`
Проверяет, является ли строка URL (`http://`, `https://`, `git@`).

---

##### `to_posix(path: Path) -> str`
Преобразует путь в строку с `/`.

---

## classify

Модуль классификации файлов по типу и домену.

### Функции

##### `classify_type(path: Path) -> str`
Определяет тип файла: `code`, `docs`, `config`, `data`, `ci`, `infra`, `other`.

---

##### `detect_domains(path: Path, content_snippet: str) -> Set[str]`
Определяет домены: `kubernetes`, `docker`, `ci` и др.

---

##### `is_infra(domains: Set[str]) -> bool`
Проверяет, относится ли файл к инфраструктуре.

---

## cache

Модуль управления кэшем на диске.

### Класс `CacheManager`

Управляет двумя файлами кэша: `index.json` и `llm_cache.json`.

#### Поля
- `cache_dir` — директория кэша.
- `index_path` — путь к `index.json`.
- `llm_cache_path` — путь к `llm_cache.json`.

#### Методы

##### `__init__(cache_dir: Path)`
Инициализирует менеджер и создаёт директорию.

---

##### `load_index() -> Dict`
Загружает индекс или возвращает пустой.

---

##### `save_index(data: Dict) -> None`
Сохраняет индекс.

---

##### `load_llm_cache() -> Dict[str, str]`
Загружает кэш LLM.

---

##### `save_llm_cache(data: Dict[str, str]) -> None`
Сохраняет кэш LLM.

---

##### `diff_files(current_files: Dict[str, Dict]) -> Tuple[Dict, Dict, Dict, Dict]`
Сравнивает текущие файлы с кэшированными.

**Возвращает**  
Кортеж: `(added, modified, deleted, unchanged)`.

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
