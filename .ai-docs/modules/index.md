# Модули

## `scanner` — сканирование исходных файлов

Модуль отвечает за рекурсивный обход файловой системы или клонирование удалённого репозитория, фильтрацию файлов по расширениям, размеру и правилам игнорирования. Результат — структурированный объект `ScanResult` с метаданными и содержимым файлов.

### Ключевые структуры

- **`ScanResult`** — результат сканирования:
  - `root: Path` — абсолютный путь к корню проекта
  - `files: List[FileEntry]` — список обработанных файлов
  - `source: str` — исходный путь или URL
  - `repo_name: str` — имя репозитория

### Основные функции

- `scan_source(source: str, include=None, exclude=None, max_size=200000) -> ScanResult`  
  Сканирует локальную директорию или клонирует Git-репозиторий. Применяет фильтрацию по:
  - `include` — glob-шаблоны включения (по умолчанию — из `.ai-docs.yaml`)
  - `exclude` — шаблоны исключения (дополняются `.gitignore`, `.build_ignore`)
  - `max_size` — файлы больше указанного размера (в байтах) игнорируются

- `_load_extension_config(root: Path) -> Dict`  
  Загружает `.ai-docs.yaml` из корня проекта. Поддерживаемые поля:
  ```yaml
  code_extensions: [".py", ".js"]
  doc_extensions: [".md", ".rst"]
  config_extensions: [".yaml", ".toml"]
  exclude: ["*.log", "temp/"]
  ```

- `_load_ignore_specs(root: Path) -> List[PathSpec]`  
  Загружает и компилирует правила из `.gitignore` и `.build_ignore` для последующей проверки путей.

- `_should_include(rel_path, include, exclude, ignore_specs) -> bool`  
  Проверяет, должен ли файл быть включён:
  1. Соответствует хотя бы одному шаблону из `include` (если задано)
  2. Не соответствует ни одному шаблону из `exclude`
  3. Не игнорируется по правилам `ignore_specs`

- `_scan_directory(root, include, exclude, max_size)`  
  Рекурсивно обходит директорию, возвращает список словарей с полями:
  - `path` — относительный путь (POSIX)
  - `abs_path` — абсолютный путь
  - `size` — размер в байтах
  - `content` — содержимое файла (если текстовый)
  - `type` — тип файла (определяется `classify_type`)
  - `domains` — домены инфраструктуры (определяется `detect_domains`)

- `_clone_repo(repo_url) -> (temp_dir, repo_name)`  
  Клонирует репозиторий в временную директорию. Использует `git clone`. Выбрасывает `RuntimeError` при ошибке.

---

## `llm` — взаимодействие с языковыми моделями

Модуль предоставляет клиент для отправки запросов к LLM через OpenAI-совместимый API с поддержкой кэширования.

### Ключевые структуры

- **`LLMClient`** — клиент для работы с LLM:
  - `api_key`, `base_url`, `model`, `temperature`, `max_tokens`, `context_limit`
  - Кэширование по SHA256-хешу тела запроса

### Основные функции

- `LLMClient.chat(messages, cache=None) -> str`  
  Отправляет список сообщений вида `{"role": "user", "content": "..."}` и возвращает ответ модели.  
  Если передан `cache`, использует его для повторных запросов.

- `from_env() -> LLMClient`  
  Создаёт клиент на основе переменных окружения:
  - `OPENAI_API_KEY` — обязательна
  - `OPENAI_BASE_URL`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` — опционально

---

## `processor` — обработка и суммаризация файлов

Модуль обрабатывает файлы, генерирует краткие описания с помощью LLM и нормализует формат.

### Основные функции

- `summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False) -> str`  
  Генерирует описание файла:
  - Для `detailed=True` — в стиле Doxygen
  - Для инфраструктурных файлов (`domains`) — с акцентом на конфигурацию
  - Результат кэшируется по хешу входных данных

- `_normalize_module_summary(summary, llm_client, llm_cache) -> str`  
  Приводит текст к строгому Doxygen-формату, если `_needs_doxygen_fix()` возвращает `True`.

- `write_summary(summary_dir, rel_path, summary) -> Path`  
  Сохраняет резюме в `summary_dir` с сохранением структуры путей. Расширение — `.md`.

---

## `generator` — генерация документации

Модуль формирует финальную документацию: README, разделы и конфигурацию MkDocs.

### Основные функции

- `generate_docs(files, output_root, cache_dir, llm, language, write_readme, write_mkdocs, use_cache=True, threads=1)`  
  Основная функция генерации:
  1. Собирает контекст (зависимости, архитектура, модули)
  2. Генерирует разделы с помощью `_generate_section`
  3. Создаёт `README.md` и/или `mkdocs.yml`
  4. Сохраняет файлы через `write_docs_files`

- `_collect_dependencies(files) -> List[str]`  
  Извлекает зависимости из `requirements.txt`, `pyproject.toml`, `package.json`.

- `_truncate_context(context, model, max_tokens)`  
  Обрезает текст, чтобы уложиться в лимит токенов (использует `tiktoken`).

---

## `mkdocs` — генерация конфигурации MkDocs

Модуль формирует `mkdocs.yml` и структуру навигации.

### Основные функции

- `build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None) -> str`  
  Генерирует YAML-конфигурацию:
  - `sections` — основные разделы (например, "Архитектура", "Запуск")
  - `configs` — конфигурационные файлы (Kubernetes, Helm)
  - `module_nav_paths` — пути к модулям для иерархической навигации

- `_build_modules_nav(module_paths) -> List[Dict]`  
  Строит дерево навигации по путям модулей (например, `src/api/users.py` → `API > Users`).

- `write_docs_files(docs_dir, files)`  
  Записывает все файлы из словаря `{относительный_путь: содержимое}` в `docs_dir`.

---

## `utils` — вспомогательные функции

### Работа с файлами и путями

- `read_text_file(path) -> str` — читает файл в UTF-8
- `ensure_dir(path)` — создаёт директорию с родителями
- `to_posix(path) -> str` — преобразует путь в POSIX-формат
- `is_binary_file(path) -> bool` — проверяет наличие нулевых байтов
- `is_url(value) -> bool` — проверяет, является ли строка URL

### Хеширование и безопасность

- `sha256_text(text) -> str` — возвращает hex-представление SHA-256
- `safe_slug(path) -> str` — заменяет спецсимволы на `_` для безопасных имён

---

## `classifier` — классификация файлов

### Основные функции

- `classify_type(path) -> str`  
  Возвращает тип файла:
  - `code`: `.py`, `.js`, `.go`
  - `config`: `.yaml`, `.json`, `.env`
  - `docs`: `.md`, `.rst`
  - `infra`: `Dockerfile`, `.tf`, `.yaml` (если содержит `apiVersion: apps/v1`)
  - `ci`: `.github/workflows`, `.gitlab-ci.yml`

- `detect_domains(path, content_snippet) -> Set[str]`  
  Определяет домены по имени, пути и содержимому:
  - `kubernetes`, `docker`, `terraform`, `ci`, `helm`

- `is_infra(domains) -> bool`  
  Проверяет, содержит ли множество доменов инфраструктурные (например, `kubernetes`).

---

## `cache` — управление кэшем

### Ключевая структура

- **`CacheManager(cache_dir)`**:
  - `index_path`, `llm_cache_path` — пути к JSON-файлам
  - `load_index()`, `save_index(data)`
  - `load_llm_cache()`, `save_llm_cache(data)`
  - `diff_files(current_files)` — возвращает `(added, modified, deleted, unchanged)` по хешам содержимого

---

## `tokenizer` — подсчёт и разбиение токенов

### Основные функции

- `count_tokens(text, model) -> int`  
  Подсчитывает токены с использованием `tiktoken`. Поддерживаемые модели: `gpt-4`, `gpt-3.5-turbo`.  
  Для остальных — резервная кодировка `cl100k_base`.

- `chunk_text(text, model, max_tokens) -> List[str]`  
  Разбивает текст на фрагменты, каждый ≤ `max_tokens`. Используется для обработки больших файлов.

---

## `cli` — точка входа

### Основные функции

- `parse_args() -> Namespace`  
  Парсит аргументы командной строки:
  - `--source`, `--output`, `--language`, `--max-size`
  - `--readme`, `--mkdocs`, `--local-site`, `--force`
  - `--cache-dir`, `--no-cache`, `--threads`

- `resolve_output(source, output, repo_name) -> Path`  
  Определяет путь вывода:
  - Если `output` не задан — создаёт `./output/<repo_name>`

- `main()`  
  Основной поток:
  1. Парсинг аргументов
  2. Сканирование исходников
  3. Генерация документации
  4. Запись результатов

---

## `__main__` — запуск приложения

- Динамически загружает `main` из `ai_docs.cli`
- Корректно работает при запуске как `python -m ai_docs` или `python main.py`
- Обрабатывает `ImportError` при отсутствии в `sys.path`

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
