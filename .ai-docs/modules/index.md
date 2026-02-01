# Модули

## Модуль `scanner`

Отвечает за сканирование исходных файлов в локальной директории или удалённом Git-репозитории. Формирует структурированный результат с метаданными, используемый на последующих этапах генерации документации.

### Ключевые структуры данных
- `ScanResult` — результат сканирования: содержит корневой путь, список файлов, источник и имя репозитория.

### Основные функции

#### `scan_source(source, include=None, exclude=None, max_size=200000) → ScanResult`
Сканирует локальную директорию или клонирует удалённый репозиторий, фильтруя файлы по расширениям и размеру.

**Аргументы:**
- `source` (`str`) — путь к локальной директории или URL Git-репозитория.
- `include` (`Set[str]`, опционально) — шаблоны включения (glob). Если не задано, определяется автоматически.
- `exclude` (`Set[str]`, опционально) — шаблоны исключения (дополняется правилами из `.gitignore` и `.build_ignore`).
- `max_size` (`int`) — максимальный размер файла в байтах (по умолчанию 200 КБ).

**Возвращает:**
- `ScanResult` — объект с результатами сканирования.

**Исключения:**
- `FileNotFoundError` — если локальный путь не существует.
- `RuntimeError` — при ошибке клонирования репозитория.

---

#### `_scan_directory(root, include, exclude, max_size) → List[Dict]`
Рекурсивно сканирует директорию и возвращает список подходящих файлов.

**Поля возвращаемых словарей:**
- `path` — относительный путь (POSIX).
- `abs_path` — абсолютный путь.
- `size` — размер файла в байтах.
- `content` — содержимое файла (если текстовый и в пределах `max_size`).
- `type` — тип файла (определяется `classify_type`).
- `domains` — домены инфраструктуры (определяется `detect_domains`).

**Исключения:**
- `OSError` — игнорируется, файл пропускается.

---

#### `_load_extension_config(root) → Dict[str, object]`
Загружает `.ai-docs.yaml` из корня проекта. Если файл отсутствует — создаёт конфиг по умолчанию.

**Возвращает:**
- Словарь с ключами: `code_extensions`, `doc_extensions`, `config_extensions`, `exclude`.

---

#### `_build_default_include_patterns(extension_config) → Set[str]`
Формирует шаблоны включения на основе расширений из конфига и фиксированных паттернов (например, `*.py`, `*.yaml`).

---

#### `_load_ignore_specs(root) → List[pathspec.PathSpec]`
Загружает и компилирует правила игнорирования из `.gitignore` и `.build_ignore`.

---

#### `_should_include(rel_path, include, exclude, ignore_specs) → bool`
Проверяет, должен ли файл быть включён в сканирование.

**Приоритет:**
1. Если `include` задан — файл должен соответствовать хотя бы одному шаблону.
2. Если `exclude` задан — файл не должен соответствовать ни одному шаблону.
3. Проверка по `ignore_specs` (`.gitignore` и др.).

---

#### `_normalize_extensions(raw, defaults) → Dict[str, str]`
Приводит пользовательские расширения к виду `{".ext": "описание"}`. Дополняет значениями по умолчанию.

---

#### `_normalize_excludes(raw) → Set[str]`
Преобразует входные данные в множество непустых строк шаблонов исключения.

---

#### `_clone_repo(repo_url) → Tuple[Path, str]`
Клонирует репозиторий в временную директорию.

**Возвращает:**
- Путь к временной директории.
- Имя репозитория (извлечено из URL).

**Исключения:**
- `RuntimeError` — при сбое клонирования.

---

### Класс `ScanResult`

Представляет результат сканирования.

**Поля:**
- `root` (`Path`) — абсолютный путь к корневой директории.
- `files` (`List[FileEntry]`) — список просканированных файлов.
- `source` (`str`) — исходный путь или URL.
- `repo_name` (`str`) — имя репозитория.

**Методы:**
- `__init__(root, files, source, repo_name)` — создаёт экземпляр.

---

## Модуль `llm`

Предоставляет клиент для взаимодействия с LLM через API, совместимый с OpenAI. Поддерживает кэширование запросов и управление контекстом.

### Ключевые структуры данных
- `LLMClient` — клиент для отправки запросов к LLM с кэшированием.

### Класс `LLMClient`

**Поля:**
- `api_key` — ключ аутентификации.
- `base_url` — базовый URL API (например, `https://api.openai.com/v1`).
- `model` — имя модели (например, `gpt-4o-mini`).
- `temperature` — параметр разнообразия ответов (по умолчанию `0.2`).
- `max_tokens` — макс. токенов в ответе.
- `context_limit` — общий лимит токенов в контексте.

**Методы:**

#### `__init__(api_key, base_url, model, temperature=0.2, max_tokens=1200, context_limit=8192)`
Инициализирует клиент.

---

#### `chat(messages, cache=None) → str`
Отправляет запрос к модели.

**Аргументы:**
- `messages` — список сообщений в формате `{"role": "user", "content": "..."}`.
- `cache` — словарь для кэширования (ключ — хеш запроса, значение — ответ).

**Возвращает:**
- Текст ответа от модели.

**Исключения:**
- `RuntimeError` — если ответ не содержит `content`.

---

#### `_cache_key(payload) → str`
Генерирует SHA256-хеш JSON-представления запроса.

---

#### `from_env() → LLMClient`
Создаёт клиент на основе переменных окружения.

**Требует:**
- `OPENAI_API_KEY`

**Исключения:**
- `RuntimeError` — если ключ не задан.

---

## Модуль `utils`

Содержит вспомогательные функции для работы с файлами, путями, хешированием и проверкой типов.

### Основные функции

#### `sha256_bytes(data) → str`
Возвращает SHA-256 хеш от байтов.

#### `sha256_text(text) → str`
Возвращает SHA-256 хеш от строки (в UTF-8).

#### `read_text_file(path) → str`
Читает текстовый файл в UTF-8.

**Исключения:**
- `OSError` — при ошибках доступа.

#### `safe_slug(path) → str`
Преобразует строку в безопасный слаг (заменяет спецсимволы на `_`).

#### `ensure_dir(path)`
Создаёт директорию и все родительские, если необходимо.

**Исключения:**
- `OSError` — при сбое создания.

#### `is_binary_file(path, sample_size=2048) → bool`
Определяет, является ли файл двоичным (по наличию нулевых байтов).

**Возвращает `True` при ошибках чтения.**

#### `is_url(value) → bool`
Проверяет, является ли строка URL (`http://`, `https://`, `git@`).

#### `to_posix(path) → str`
Преобразует путь в POSIX-формат (с `/`).

---

## Модуль `classifier`

Предназначен для автоматической классификации файлов по типу и доменам инфраструктуры.

### Основные функции

#### `classify_type(path) → str`
Определяет тип файла по расширению или имени.

**Возвращает:**
- `"code"`, `"config"`, `"docs"`, `"infra"`, `"ci"`, `"data"`, `"other"`.

#### `detect_domains(path, content_snippet) → Set[str]`
Определяет домены по имени файла, пути и фрагменту содержимого.

**Примеры доменов:**
- `"kubernetes"`, `"docker"`, `"terraform"`, `"ci"`, `"helm"`.

#### `is_infra(domains) → bool`
Проверяет, относится ли файл к инфраструктурным доменам.

---

## Модуль `tokenizer`

Работает с токенизацией текста для LLM. Использует `tiktoken` для подсчёта и разбиения токенов.

### Основные функции

#### `get_encoding(model) → Encoding`
Возвращает кодировку для модели. Если модель не поддерживается — использует `cl100k_base`.

#### `count_tokens(text, model) → int`
Подсчитывает количество токенов в тексте.

#### `chunk_text(text, model, max_tokens) → List[str]`
Разбивает текст на части, не превышающие `max_tokens`.

---

## Модуль `cache`

Управляет кэшем файлов и LLM-ответов на диске.

### Класс `CacheManager`

**Поля:**
- `cache_dir` — директория хранения кэша.
- `index_path` — путь к `index.json`.
- `llm_cache_path` — путь к `llm_cache.json`.

**Методы:**

#### `__init__(cache_dir)`
Создаёт директорию кэша и файлы, если отсутствуют.

#### `load_index() → Dict`
Загружает индекс файлов. Возвращает пустой словарь, если файл не найден.

#### `save_index(data)`
Сохраняет индекс в `index.json`.

#### `load_llm_cache() → Dict[str, str]`
Загружает кэш LLM. Возвращает пустой словарь при отсутствии.

#### `save_llm_cache(data)`
Сохраняет кэш LLM.

#### `diff_files(current_files) → Tuple[added, modified, deleted, unchanged]`
Сравнивает текущие файлы с предыдущим состоянием.

**Используется для определения изменений в проекте.**

---

## Модуль `generator`

Генерирует документацию на основе просканированных файлов и метаданных.

### Основные функции

#### `summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False) → str`
Генерирует резюме содержимого файла.

**Типы:**
- `"config"` — нормализуется в универсальный формат.
- `"module"` — приводится к Doxygen-стилю.

#### `_normalize_module_summary(summary, llm_client, llm_cache) → str`
Приводит описание модуля к строгому Doxygen-формату.

#### `_normalize_config_summary(summary, llm_client, llm_cache) → str`
Нормализует описание конфигурации.

#### `_format_config_blocks(text) → str`
Форматирует секции конфигурации: объединяет строки через `<br>`, разделяет блоки пустыми строками.

#### `_needs_doxygen_fix(text) → bool`
Проверяет, содержит ли текст Markdown-разметку или списки.

#### `_strip_fenced_markdown(text) → str`
Удаляет ``` из начала и конца текста.

#### `write_summary(summary_dir, rel_path, summary) → Path`
Сохраняет резюме в Markdown-файл. Создаёт промежуточные директории.

---

## Модуль `docs`

Формирует структуру документации и генерирует `mkdocs.yml`.

### Основные функции

#### `build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None, project_config_nav_paths=None) → str`
Генерирует YAML-конфигурацию для MkDocs.

**Особенности:**
- При `local_site=True` отключает `site_url` и `use_directory_urls`.
- Строит навигацию по секциям и доменам.

#### `_build_tree_nav(paths, strip_prefix) → List[Dict]`
Строит древовидную навигацию из списка путей.

#### `_insert_nav_node(tree, parts, rel_path)`
Рекурсивно вставляет узел в дерево.

#### `_tree_to_nav(tree) → List[Dict]`
Преобразует дерево в список для MkDocs.

#### `write_docs_files(docs_dir, files)`
Записывает все документы на диск. Создаёт директории при необходимости.

**Исключения:**
- `IOError`, `OSError` — при ошибках записи.

---

## Модуль `changes`

Формирует отчёт об изменениях в проекте.

### Функция `format_changes_md(added, modified, deleted, regenerated_sections, summary) → str`

**Аргументы:**
- `added`, `modified`, `deleted` — словари с путями файлов.
- `regenerated_sections` — список перегенерированных разделов.
- `summary` — краткое резюме изменений от LLM.

**Возвращает:**
- Отчёт в формате Markdown с заголовками и списками.

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
