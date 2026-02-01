# Модули

## `scanner` — Сканирование исходных файлов

Модуль отвечает за рекурсивный анализ файловой структуры проекта (локального или удалённого через Git) и формирование метаданных для последующей обработки. Поддерживает фильтрацию по расширениям, размеру файлов и правилам игнорирования (`.gitignore`, `.build_ignore`).

### Ключевые структуры данных

- **`ScanResult`** — результат сканирования:
  - `root: Path` — абсолютный путь к корневой директории.
  - `files: List[FileEntry]` — список обработанных файлов.
  - `source: str` — исходный путь или URL.
  - `repo_name: str` — имя репозитория.

### Основные функции

- `scan_source(source: str, include=None, exclude=None, max_size=200000) -> ScanResult`  
  Сканирует локальную директорию или клонирует удалённый репозиторий. Применяет фильтры включения/исключения и ограничение по размеру.  
  **Исключения**: `FileNotFoundError` — если локальный путь не существует.

- `_load_extension_config(root: Path) -> Dict`  
  Загружает `.ai-docs.yaml` из корня проекта. Возвращает конфиг с полями: `code_extensions`, `doc_extensions`, `config_extensions`, `exclude`.

- `_load_ignore_specs(root: Path) -> List[PathSpec]`  
  Компилирует правила из `.gitignore` и `.build_ignore` для последующей проверки соответствия путей.

- `_should_include(rel_path, include, exclude, ignore_specs) -> bool`  
  Проверяет, должен ли файл быть включён в результат. Учитывает glob-паттерны, исключения и `.gitignore`.

- `_scan_directory(root, include, exclude, max_size) -> List[Dict]`  
  Рекурсивно сканирует директорию. Возвращает список словарей с полями: `path`, `abs_path`, `size`, `content`, `type`, `domains`.  
  **Исключения**: `OSError` — игнорируются, файл пропускается.

---

## `main` — Точка входа CLI

Модуль обрабатывает аргументы командной строки, инициирует сканирование, настраивает LLM и запускает генерацию документации.

### Аргументы командной строки

| Аргумент | Описание |
|--------|--------|
| `--source` | Путь к папке или URL Git-репозитория (обязательный) |
| `--output` | Директория вывода (по умолчанию: `./output/<repo>`) |
| `--readme` | Генерировать `README.md` |
| `--mkdocs` | Генерировать MkDocs-сайт |
| `--language` | Язык документации (`ru` или `en`, по умолчанию: `ru`) |
| `--max-size` | Макс. размер файла в байтах (по умолчанию: 200 000) |
| `--no-cache` | Отключить кэширование LLM |
| `--threads` | Количество потоков обработки |

### Основные функции

- `parse_args() -> Namespace`  
  Парсит аргументы CLI. Не выбрасывает исключения.

- `resolve_output(source, output, repo_name) -> Path`  
  Определяет итоговую директорию вывода на основе входных параметров.

- `main()`  
  Основная логика: сканирование → генерация → запись.  
  **Исключения**: возможны при ошибках доступа к LLM, файловой системе или сети.

---

## `llm` — Взаимодействие с языковой моделью

Предоставляет клиент для отправки запросов к LLM с поддержкой кэширования и управления контекстом.

### Класс `LLMClient`

- **Поля**:
  - `api_key`, `base_url`, `model`, `temperature`, `max_tokens`, `context_limit`

- **Методы**:
  - `__init__()` — инициализация клиента.
  - `chat(messages: list[dict], cache: dict = None) -> str` — отправка запроса.  
    **Исключения**: `RuntimeError`, если ответ не содержит контента.
  - `_cache_key(payload) -> str` — генерация SHA256-хеша тела запроса.
  - `from_env() -> LLMClient` — создание клиента из переменных окружения.  
    **Исключения**: `RuntimeError`, если `OPENAI_API_KEY` не задан.

---

## `summarizer` — Генерация и нормализация описаний

Модуль обрабатывает содержимое файлов, генерирует и форматирует резюме с помощью LLM.

### Основные функции

- `summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False) -> str`  
  Генерирует Markdown-резюме файла с учётом типа и доменов.

- `_normalize_module_summary(summary, llm_client, llm_cache) -> str`  
  Приводит описание модуля к Doxygen-формату.

- `_normalize_config_summary(summary, llm_client, llm_cache) -> str`  
  Нормализует описание конфигурационного файла.

- `_needs_doxygen_fix(text) -> bool`  
  Проверяет, содержит ли текст Markdown-элементы, требующие очистки.

- `_strip_fenced_markdown(text) -> str`  
  Удаляет ``` из начала и конца текста.

- `chunk_text(content, model, max_tokens) -> List[str]`  
  Разбивает текст на части по лимиту токенов.

- `write_summary(summary_dir, rel_path, summary) -> Path`  
  Сохраняет резюме в файл `.md`. Возвращает путь к созданному файлу.

---

## `builder` — Генерация документации и MkDocs

Формирует структуру документации, генерирует `mkdocs.yml` и записывает файлы на диск.

### Основные функции

- `build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None, project_config_nav_paths=None) -> str`  
  Генерирует YAML-конфигурацию для MkDocs.

- `_build_tree_nav(paths, strip_prefix) -> List[Dict]`  
  Строит иерархическую навигацию из списка путей.

- `_insert_nav_node(tree, parts, rel_path)`  
  Вставляет узел в дерево навигации по частям пути.

- `_tree_to_nav(tree) -> List[Dict]`  
  Преобразует дерево в упорядоченный список для MkDocs (папки перед файлами).

- `write_docs_files(docs_dir, files)`  
  Записывает все файлы из словаря `path → content`.  
  **Исключения**: возможны при ошибках ввода-вывода.

---

## `utils` — Вспомогательные функции

Набор утилит для работы с путями, хешированием, типами файлов и URL.

### Основные функции

- `sha256_bytes(data: bytes) -> str` — хеш от байтов.
- `sha256_text(text: str) -> str` — хеш от строки UTF-8.
- `read_text_file(path: Path) -> str` — чтение текстового файла.  
  **Исключения**: `OSError` при ошибках доступа.
- `safe_slug(path: str) -> str` — преобразует строку в безопасный слаг.
- `ensure_dir(path: Path)` — создаёт директорию и родителей.  
  **Исключения**: `OSError` при сбое создания.
- `is_binary_file(path: Path, sample_size=2048) -> bool` — проверка на двоичный файл.  
  **Исключения**: при ошибках доступа возвращает `True`.
- `is_url(value: str) -> bool` — проверка, является ли строка URL (`http://`, `https://`, `git@`).
- `to_posix(path: Path) -> str` — преобразует путь в POSIX-формат (`/`).

---

## `classifier` — Классификация файлов

Определяет тип файла и связанные инфраструктурные домены.

### Основные функции

- `classify_type(path: Path) -> str`  
  Возвращает тип: `code`, `docs`, `config`, `data`, `ci`, `infra`, `other`.

- `detect_domains(path: Path, content_snippet: str) -> Set[str]`  
  Определяет домены по имени, пути и содержимому (например, `kubernetes`, `docker`, `ci`).

- `is_infra(domains: Set[str]) -> bool`  
  Проверяет, относится ли файл к инфраструктуре.

---

## `cache` — Управление кэшем

Хранит и обновляет индекс файлов и кэш LLM-ответов в JSON-файлах.

### Класс `CacheManager`

- **Поля**:
  - `cache_dir`, `index_path`, `llm_cache_path`

- **Методы**:
  - `__init__(cache_dir)` — создаёт директорию и файлы кэша.
  - `load_index() -> Dict` — загружает индекс. Если нет — возвращает `{}`.
  - `save_index(data)` — сохраняет индекс.
  - `load_llm_cache() -> Dict[str, str]` — загружает кэш LLM.
  - `save_llm_cache(data)` — сохраняет кэш LLM.
  - `diff_files(current_files) -> (added, modified, deleted, unchanged)`  
    Сравнивает текущие файлы с предыдущим состоянием.

---

## `tokenizer` — Подсчёт и разбиение токенов

Работает с `tiktoken` для оценки длины текста и его фрагментации.

### Основные функции

- `get_encoding(model: str)`  
  Возвращает кодировку модели или `cl100k_base` по умолчанию.

- `count_tokens(text: str, model: str) -> int`  
  Подсчитывает токены в тексте.

- `chunk_text(text: str, model: str, max_tokens: int) -> List[str]`  
  Разбивает текст на части, укладываясь в лимит токенов.

---

## `changes` — Формирование отчёта об изменениях

Генерирует Markdown-отчёт о добавленных, изменённых и удалённых файлах.

### Функция

- `format_changes_md(added, modified, deleted, regenerated_sections, summary) -> str`  
  Возвращает отчёт в формате Markdown с заголовками и списками.  
  **Исключения**: отсутствуют.

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
