# Модули

## `scanner` — сканирование исходных файлов

Модуль отвечает за рекурсивный анализ файловой структуры проекта (локального или удалённого), фильтрацию файлов по расширениям, размеру и правилам игнорирования. Результат — объект `ScanResult`, содержащий метаданные и содержимое подходящих файлов.

### Ключевые структуры

- **`ScanResult`** — результат сканирования:
  - `root: Path` — абсолютный путь к корневой директории.
  - `files: List[FileEntry]` — список обработанных файлов.
  - `source: str` — исходный путь или URL.
  - `repo_name: str` — имя репозитория.

### Основные функции

- `scan_source(source: str, include=None, exclude=None, max_size=200000) -> ScanResult`  
  Сканирует локальную директорию или клонирует Git-репозиторий. Применяет фильтры включения/исключения, ограничение по размеру.  
  **Исключения**: `FileNotFoundError` — если путь не существует; `RuntimeError` — при ошибке клонирования.

- `_load_extension_config(root: Path) -> Dict[str, object]`  
  Загружает `.ai-docs.yaml` из корня проекта. Возвращает конфиг с полями: `code_extensions`, `doc_extensions`, `config_extensions`, `exclude`.

- `_load_ignore_specs(root: Path) -> List[pathspec.PathSpec]`  
  Загружает и компилирует правила из `.gitignore` и `.build_ignore`.

- `_should_include(rel_path: str, include, exclude, ignore_specs) -> bool`  
  Проверяет, должен ли файл быть включён. Учитывает glob-паттерны, исключения и `.gitignore`.

- `_scan_directory(root, include, exclude, max_size) -> List[Dict]`  
  Рекурсивно сканирует директорию. Возвращает список словарей с полями: `path`, `abs_path`, `size`, `content`, `type`, `domains`.  
  **Исключения**: `OSError` — игнорируются, файл пропускается.

---

## `cli` — точка входа и обработка аргументов

Модуль реализует CLI-интерфейс: парсинг аргументов, инициализацию, запуск генерации документации.

### Основные функции

- `parse_args() -> argparse.Namespace`  
  Парсит командную строку:
  - `--source` — путь или URL (обязательный).
  - `--output` — директория вывода.
  - `--readme`, `--mkdocs` — флаги генерации.
  - `--language` — язык (`ru`/`en`).
  - `--max-size`, `--include`, `--exclude` — фильтрация файлов.
  - `--cache-dir`, `--no-cache` — управление кэшем.
  - `--threads` — параллельная обработка.
  - `--force` — перезапись README.

- `resolve_output(source, output, repo_name) -> Path`  
  Определяет путь вывода: если не задан — использует `./output/<repo_name>`.

- `main()`  
  Основная логика: сканирование, инициализация LLM, генерация README и/или MkDocs.  
  **Исключения**: возможны при ошибках доступа к LLM, файловой системе или сети.

---

## `llm` — взаимодействие с языковой моделью

Модуль предоставляет клиент для отправки запросов к LLM с поддержкой кэширования и управления контекстом.

### Ключевые структуры

- **`LLMClient`** — клиент для работы с LLM:
  - `api_key`, `base_url`, `model` — параметры подключения.
  - `temperature`, `max_tokens`, `context_limit` — настройки генерации.
  - Методы:
    - `chat(messages, cache=None)` — отправляет запрос, возвращает ответ.
    - `_cache_key(payload)` — генерирует SHA256-хеш тела запроса.
    - `from_env()` — создаёт клиент из переменных окружения (`OPENAI_API_KEY`, `LLM_MODEL` и др.).

---

## `summarizer` — генерация и нормализация описаний

Модуль обрабатывает содержимое файлов: генерирует резюме, нормализует формат, разбивает на чанки.

### Основные функции

- `summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False) -> str`  
  Генерирует Markdown-резюме файла. Типы: `config`, `infra`, `module`.

- `_normalize_module_summary(summary, llm_client, llm_cache) -> str`  
  Приводит описание модуля к Doxygen-формату.

- `_normalize_config_summary(summary, llm_client, llm_cache) -> str`  
  Нормализует описание конфигурации.

- `_needs_doxygen_fix(text) -> bool`  
  Проверяет, содержит ли текст Markdown-списки или заголовки.

- `_strip_fenced_markdown(text) -> str`  
  Удаляет ``` из начала и конца текста.

- `chunk_text(content, model, max_tokens) -> List[str]`  
  Разбивает текст на части по лимиту токенов.

- `write_summary(summary_dir, rel_path, summary) -> Path`  
  Сохраняет резюме в `summary_dir` с именем, производным от `rel_path`.

---

## `mkdocs` — генерация конфигурации и запись документации

Модуль формирует `mkdocs.yml` и сохраняет Markdown-файлы на диск.

### Основные функции

- `build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None, project_config_nav_paths=None) -> str`  
  Генерирует YAML-конфиг для MkDocs с навигацией по разделам.

- `_build_tree_nav(paths, strip_prefix) -> List[Dict]`  
  Строит иерархию навигации из списка путей.

- `_insert_nav_node(tree, parts, rel_path)`  
  Вставляет узел в дерево по частям пути.

- `_tree_to_nav(tree) -> List[Dict]`  
  Преобразует дерево в отсортированный список для MkDocs.

- `write_docs_files(docs_dir, files)`  
  Записывает файлы из словаря `path: content` в `docs_dir`, создавая директории при необходимости.

---

## `utils` — вспомогательные функции

Набор утилит для работы с файлами, путями, хешированием и типами данных.

### Основные функции

- `sha256_bytes(data: bytes) -> str`, `sha256_text(text: str) -> str` — вычисление SHA-256.
- `read_text_file(path: Path) -> str` — чтение файла в UTF-8.  
  **Исключения**: `OSError` — при ошибках доступа.
- `safe_slug(path: str) -> str` — преобразует строку в безопасный слаг.
- `ensure_dir(path: Path)` — создаёт директорию и родителей.  
  **Исключения**: `OSError` — при сбое создания.
- `is_binary_file(path: Path, sample_size=2048) -> bool` — проверка на двоичный файл по наличию `\x00`.
- `is_url(value: str) -> bool` — проверка, является ли строка URL (`http://`, `https://`, `git@`).
- `to_posix(path: Path) -> str` — преобразует путь в POSIX-формат (`/`).

---

## `classifier` — классификация файлов

Определяет тип файла и домены инфраструктуры.

### Основные функции

- `classify_type(path: Path) -> str`  
  Возвращает тип: `code`, `docs`, `config`, `data`, `ci`, `infra`, `other`.

- `detect_domains(path: Path, content_snippet: str) -> Set[str]`  
  Определяет домены по имени, пути и содержимому: `kubernetes`, `docker`, `terraform`, `ci`.

- `is_infra(domains: Set[str]) -> bool`  
  Проверяет, относится ли файл к инфраструктуре.

---

## `cache` — управление кэшем

Модуль хранит индекс файлов и кэш LLM-ответов в JSON-файлах.

### Ключевая структура

- **`CacheManager`**:
  - `cache_dir: Path` — директория кэша.
  - Методы:
    - `load_index() -> Dict` — загружает `index.json`.
    - `save_index(data)` — сохраняет индекс.
    - `load_llm_cache() -> Dict[str, str]` — загружает кэш LLM.
    - `save_llm_cache(data)` — сохраняет кэш.
    - `diff_files(current_files) -> (added, modified, deleted, unchanged)` — сравнивает текущее и предыдущее состояние.

---

## `changes` — формирование отчёта об изменениях

Генерирует Markdown-отчёт о добавленных, изменённых и удалённых файлах.

### Основная функция

- `format_changes_md(added, modified, deleted, regenerated_sections, summary) -> str`  
  Возвращает отчёт с заголовками и маркированными списками.  
  **Аргументы**: словари файлов, список секций, краткое резюме.

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
