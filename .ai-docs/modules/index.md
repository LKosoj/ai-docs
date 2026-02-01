# Модули

## Сканирование файловой системы и репозиториев

Модуль отвечает за сканирование локальных директорий или удалённых Git-репозиториев с целью сбора информации о файлах, подходящих для анализа и документирования. Учитывает пользовательские и встроенные правила включения/исключения, обрабатывает конфигурацию из `.ai-docs.yaml`, игнорирует бинарные и слишком большие файлы. Результат — структурированный список файлов с метаданными.

### `ScanResult`

Результат сканирования исходного кода, содержащий путь к корню, список файлов, источник и имя репозитория.

**Поля:**
- `root` — корневой путь сканирования (`Path`)
- `files` — список словарей с информацией о каждом файле
- `source` — источник сканирования (локальный путь или URL)
- `repo_name` — имя репозитория

**Методы:**
- `__init__(self, root: Path, files: List[Dict], source: str, repo_name: str)` — инициализирует объект с указанными параметрами.

### Основные функции

#### `_normalize_extensions(raw: object, defaults: Dict[str, str]) -> Dict[str, str]`
Нормализует пользовательские расширения из конфигурации: добавляет точки (`.py`) и описания.  
Если `raw` — список, используется как ключи, значения берутся из `defaults`.  
Если `raw` — словарь, применяется напрямую с дополнением описаний.

#### `_normalize_excludes(raw: object) -> Set[str]`
Преобразует входные данные в набор строковых шаблонов исключения. Поддерживает списки и словари. Возвращает нормализованные glob-паттерны.

#### `_load_extension_config(root: Path) -> Dict[str, object]`
Загружает конфигурацию из `.ai-docs.yaml` в корне проекта. Если файл отсутствует — возвращает встроенные значения.  
Возвращает словарь с ключами:
- `code_extensions`
- `doc_extensions`
- `config_extensions`
- `exclude`

#### `_build_default_include_patterns(extension_config: Dict[str, object]) -> Set[str]`
Формирует набор glob-паттернов включения (например, `*.py`, `*.md`) на основе расширений из конфигурации. Включает фиксированные паттерны для часто используемых файлов (например, `Dockerfile`, `.env`).

#### `_load_ignore_specs(root: Path) -> List[pathspec.PathSpec]`
Загружает и компилирует правила игнорирования из `.gitignore` и `.build_ignore`. Возвращает список объектов `PathSpec` для проверки путей.

#### `_should_include(rel_path: str, include: Optional[Set[str]], exclude: Optional[Set[str]], ignore_specs: List[pathspec.PathSpec]) -> bool`
Проверяет, должен ли файл быть включён:
1. Соответствует хотя бы одному паттерну из `include` (если задано)
2. Не соответствует ни одному паттерну из `exclude`
3. Не игнорируется по правилам из `ignore_specs`

#### `_scan_directory(root: Path, include: Optional[Set[str]], exclude: Optional[Set[str]], max_size: int) -> List[Dict]`
Рекурсивно сканирует директорию. Для каждого файла:
- Проверяется включение через `_should_include`
- Определяется тип и домены через `classify_type` и `detect_domains`
- Проверяется, не является ли файл бинарным (`is_binary_file`)
- Считывается содержимое (если размер ≤ `max_size`)
- Формируется словарь с полями: `path`, `content`, `type`, `domains`, `size`

#### `_clone_repo(repo_url: str) -> Tuple[Path, str]`
Клонирует Git-репозиторий в временную директорию. Возвращает путь к ней и имя репозитория (из URL).  
**Исключения:** `RuntimeError`, если клонирование не удалось.

#### `scan_source(source: str, include: Optional[Set[str]] = None, exclude: Optional[Set[str]] = None, max_size: int = 200_000) -> ScanResult`
Основная точка входа. Определяет тип источника:
- Если `source` — URL: клонирует репозиторий через `_clone_repo`
- Если путь: проверяет существование, иначе — `FileNotFoundError`

Затем:
1. Загружает конфигурацию расширений
2. Формирует паттерны включения/исключения
3. Сканирует директорию через `_scan_directory`
4. Возвращает `ScanResult`

---

## Утилиты для работы с файлами и путями

Модуль предоставляет набор функций для безопасной и кроссплатформенной работы с файлами, путями, хешированием и проверкой типов.

### Основные функции

#### `sha256_bytes(data: bytes) -> str`
Возвращает SHA-256 хеш байтовых данных в виде hex-строки.

#### `sha256_text(text: str) -> str`
Вычисляет SHA-256 от строки, предварительно закодированной в UTF-8.

#### `read_text_file(path: Path) -> str`
Считывает текстовый файл в кодировке UTF-8.  
**Исключения:** `OSError`, если файл недоступен.

#### `safe_slug(path: str) -> str`
Преобразует строку в безопасный слаг: заменяет все неалфавитно-цифровые символы на `_`.

#### `ensure_dir(path: Path) -> None`
Создаёт директорию и все родительские, если они отсутствуют.  
**Исключения:** `OSError`, если создание невозможно.

#### `is_binary_file(path: Path, sample_size: int = 2048) -> bool`
Определяет, является ли файл бинарным, анализируя первые `sample_size` байт на наличие нулевых байтов.  
При ошибках доступа возвращает `True`.

#### `is_url(value: str) -> bool`
Проверяет, начинается ли строка с `http://`, `https://` или `git@`.

#### `to_posix(path: Path) -> str`
Преобразует путь в строку с `/`, независимо от ОС.

---

## Классификация файлов

Модуль определяет тип файла и связанные с ним инфраструктурные домены.

### Основные функции

#### `classify_type(path: Path) -> str`
Определяет тип файла по расширению или имени:
- `code`: `.py`, `.js`, `.go` и др.
- `config`: `.yaml`, `.toml`, `.env`
- `docs`: `.md`, `.rst`
- `ci`: `.github/workflows`, `.gitlab-ci.yml`
- `infra`: `Dockerfile`, `k8s/`, `terraform/`
- `data`: `.json`, `.csv`
- `other`: всё остальное

#### `detect_domains(path: Path, content_snippet: str) -> Set[str]`
Определяет домены по пути и фрагменту содержимого. Поддерживаемые домены:
- `kubernetes`
- `docker`
- `terraform`
- `helm`
- `ci`
- `aws`
- `gcp`

#### `is_infra(domains: Set[str]) -> bool`
Возвращает `True`, если хотя бы один из доменов относится к инфраструктуре.

---

## Токенизация и разбиение текста

Модуль предоставляет инструменты для подсчёта токенов и разбиения текста на части с учётом ограничений модели.

### Основные функции

#### `get_encoding(model: str)`
Возвращает кодировку `tiktoken` для указанной модели. Если модель не поддерживается — возвращает `cl100k_base`.

#### `count_tokens(text: str, model: str) -> int`
Подсчитывает количество токенов в тексте с использованием кодировки модели.

#### `chunk_text(text: str, model: str, max_tokens: int) -> List[str]`
Разбивает текст на части, каждая из которых содержит не более `max_tokens` токенов. Сохраняет целостность строк.

---

## Кэширование

Модуль управляет кэшем файлов и LLM-ответов.

### `CacheManager`

Менеджер кэша, хранящий данные в JSON-файлах.

**Поля:**
- `cache_dir` — директория кэша
- `index_path` — путь к `index.json`
- `llm_cache_path` — путь к `llm_cache.json`

**Методы:**
- `__init__(cache_dir: Path)` — создаёт директорию и файлы при необходимости
- `load_index() -> Dict` — загружает индекс, возвращает пустой словарь при отсутствии
- `save_index(data: Dict)` — сохраняет индекс
- `load_llm_cache() -> Dict[str, str]` — загружает кэш LLM
- `save_llm_cache(data: Dict[str, str])` — сохраняет кэш LLM
- `diff_files(current_files: Dict[str, Dict]) -> Tuple[Dict, Dict, Dict, Dict]` — сравнивает текущие файлы с предыдущим состоянием, возвращает словари: добавленных, изменённых, удалённых, неизменённых

---

## LLM-клиент

Модуль предоставляет клиент для взаимодействия с LLM через API с поддержкой кэширования.

### `LLMClient`

**Поля:**
- `api_key` — ключ API
- `base_url` — URL сервера (например, `https://api.openai.com/v1`)
- `model` — имя модели
- `temperature` — температура генерации (по умолчанию `0.2`)
- `max_tokens` — максимум токенов в ответе
- `context_limit` — общий лимит контекста

**Методы:**
- `__init__()` — инициализирует клиент
- `_cache_key(payload: dict) -> str` — генерирует SHA256-хеш тела запроса
- `chat(messages: list[dict], cache: dict | None = None) -> str` — отправляет запрос, возвращает текст ответа. Использует кэш при наличии.
- `from_env() -> LLMClient` — создаёт клиент из переменных окружения. Требует `OPENAI_API_KEY`.  
  **Исключения:** `RuntimeError`, если ключ не задан.

## Список модулей

- [modules/ai_docs/__init____py](ai_docs/__init____py.md)
- [modules/ai_docs/__main____py](ai_docs/__main____py.md)
- [modules/ai_docs/cache__py](ai_docs/cache__py.md)
- [modules/ai_docs/changes__py](ai_docs/changes__py.md)
- [modules/ai_docs/cli__py](ai_docs/cli__py.md)
- [modules/ai_docs/domain__py](ai_docs/domain__py.md)
- [modules/ai_docs/generator__py](ai_docs/generator__py.md)
- [modules/ai_docs/llm__py](ai_docs/llm__py.md)
- [modules/ai_docs/mkdocs__py](ai_docs/mkdocs__py.md)
- [modules/ai_docs/scanner__py](ai_docs/scanner__py.md)
- [modules/ai_docs/summary__py](ai_docs/summary__py.md)
- [modules/ai_docs/tokenizer__py](ai_docs/tokenizer__py.md)
- [modules/ai_docs/utils__py](ai_docs/utils__py.md)
