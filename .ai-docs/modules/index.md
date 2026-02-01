# Модули

## `scan` — сканирование исходных файлов

Модуль отвечает за рекурсивный анализ файловой структуры проекта: локальной директории или удалённого Git-репозитория. Формирует объект `ScanResult` с метаданными и содержимым подходящих файлов, применяя фильтрацию по расширениям, размеру и правилам игнорирования.

### Ключевые структуры

- **`ScanResult`** — результат сканирования.
  - `root: Path` — абсолютный путь к корню сканирования.
  - `files: List[FileEntry]` — список обработанных файлов.
  - `source: str` — исходный путь или URL.
  - `repo_name: str` — имя репозитория (из URL или имени директории).

### Основные функции

- **`scan_source(source, include=None, exclude=None, max_size=200000)`**  
  Сканирует локальную директорию или клонирует репозиторий. Применяет фильтры включения/исключения, ограничение по размеру.  
  Возвращает `ScanResult`.  
  Исключения: `FileNotFoundError` — если локальный путь не существует.

- **`_load_extension_config(root)`**  
  Загружает `.ai-docs.yaml` из корня проекта. Возвращает конфиг с полями:  
  `code_extensions`, `doc_extensions`, `config_extensions`, `exclude`.

- **`_load_ignore_specs(root)`**  
  Читает `.gitignore` и `.build_ignore`, компилирует в `pathspec.PathSpec`. Используется для фильтрации файлов.

- **`_should_include(rel_path, include, exclude, ignore_specs)`**  
  Проверяет, должен ли файл быть включён. Учитывает glob-паттерны, исключения и `.gitignore`.

- **`_scan_directory(root, include, exclude, max_size)`**  
  Рекурсивно обходит директорию, читает содержимое текстовых файлов. Возвращает список словарей с полями:  
  `path`, `abs_path`, `size`, `content`, `type`, `domains`.

- **`_clone_repo(repo_url)`**  
  Клонирует репозиторий во временную директорию. Возвращает `(temp_path, repo_name)`.  
  Исключения: `RuntimeError` — при ошибке клонирования.

---

## `cli` — точка входа и обработка аргументов

Модуль обрабатывает командную строку, инициирует сканирование, настраивает LLM и запускает генерацию документации.

### Основные функции

- **`parse_args()`**  
  Парсит аргументы:
  - `--source` — путь или URL (обязательный).
  - `--output` — директория вывода.
  - `--readme`, `--mkdocs` — флаги генерации.
  - `--language` — язык (`ru`/`en`).
  - `--include`, `--exclude` — фильтры файлов.
  - `--max-size` — лимит размера файла.
  - `--cache-dir`, `--no-cache` — управление кэшем.
  - `--threads` — количество потоков.
  - `--local-site` — конфиг для локального MkDocs.
  - `--force` — перезапись README.

- **`resolve_output(source, output, repo_name)`**  
  Определяет путь вывода: если не задан — создаёт `./output/<repo_name>`.

- **`main()`**  
  Основная логика: парсинг, сканирование, инициализация LLM, генерация документации.  
  Исключения: могут возникать при ошибках доступа, LLM или записи файлов.

---

## `llm` — взаимодействие с языковой моделью

Клиент для отправки запросов к LLM с поддержкой кэширования и управления контекстом.

### Ключевые структуры

- **`LLMClient`** — клиент API.
  - Поля: `api_key`, `base_url`, `model`, `temperature`, `max_tokens`, `context_limit`.
  - Методы:
    - `__init__()` — инициализация клиента.
    - `chat(messages, cache=None)` — отправка запроса, возвращает ответ. Кэширует по хешу тела.
    - `_cache_key(payload)` — генерирует SHA256-хеш запроса.
    - `from_env()` — создаёт клиент из переменных окружения (`OPENAI_API_KEY`, `LLM_BASE_URL` и др.).

---

## `summarize` — генерация описаний файлов

Модуль анализирует содержимое файлов с помощью LLM и формирует краткие или детализированные описания.

### Основные функции

- **`summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False)`**  
  Генерирует описание файла. Для `detailed=True` — в стиле Doxygen.

- **`_normalize_module_summary(summary, llm_client, llm_cache)`**  
  Приводит текст к строгому Doxygen-формату, если обнаружены отклонения (`_needs_doxygen_fix`).

- **`_strip_fenced_markdown(text)`**  
  Удаляет ``` из начала и конца строки.

- **`write_summary(summary_dir, rel_path, summary)`**  
  Сохраняет резюме в `summary_dir` с сохранением структуры путей. Возвращает путь к файлу.

---

## `mkdocs` — генерация конфигурации MkDocs

Формирует `mkdocs.yml` и управляют структурой документации.

### Основные функции

- **`build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None)`**  
  Генерирует YAML-конфиг для MkDocs. Поддерживает навигацию по модулям.

- **`_build_modules_nav(module_paths)`**  
  Строит иерархическую навигацию по списку путей к модулям.

- **`_insert_nav_node(tree, parts, rel_path)`**, **`_tree_to_nav(tree)`** — вспомогательные функции для построения дерева.

- **`write_docs_files(docs_dir, files)`**  
  Записывает словарь `{относительный_путь: содержимое}` в `docs_dir`, создавая промежуточные директории.

---

## `docs` — генерация технической документации

Создаёт README, архитектуру, зависимости и другие разделы на основе анализа кода.

### Основные функции

- **`generate_docs(files, output_root, cache_dir, llm, language, write=True)`**  
  Генерирует полный набор документов. Возвращает словарь `{путь: содержимое}`.

- **`_generate_section(llm, llm_cache, title, context, language)`**  
  Генерирует один раздел (например, "Архитектура") с поддержкой Mermaid-диаграмм.

- **`_collect_dependencies(files)`**  
  Извлекает зависимости из `requirements.txt`, `pyproject.toml`, `package.json`.

- **`_truncate_context(context, model, max_tokens)`**  
  Обрезает текст до указанного лимита токенов.

- **`_build_docs_index(...)`**  
  Формирует `_index.json` с метаданными документации.

---

## `utils` — вспомогательные функции

Набор утилит для работы с файлами, путями, хешированием и проверкой типов.

### Основные функции

- **`sha256_text(text)`**, **`sha256_bytes(data)`** — вычисление хеша.
- **`read_text_file(path)`** — чтение файла в UTF-8.
- **`ensure_dir(path)`** — создание директории с родителями.
- **`is_binary_file(path)`** — проверка на двоичный файл по наличию нулевых байтов.
- **`is_url(value)`** — проверка строки на URL (`http://`, `https://`, `git@`).
- **`to_posix(path)`** — преобразование пути в POSIX-формат (`/`).

---

## `classify` — классификация файлов

Определяет тип файла и связанные инфраструктурные домены.

### Основные функции

- **`classify_type(path)`**  
  Возвращает тип: `code`, `docs`, `config`, `data`, `ci`, `infra`, `other`.

- **`detect_domains(path, content_snippet)`**  
  Определяет домены по имени, пути и содержимому: `kubernetes`, `docker`, `terraform`, `ci` и др.

- **`is_infra(domains)`**  
  Проверяет, относится ли файл к инфраструктуре.

---

## `cache` — управление кэшем

Хранит и сравнивает состояние файлов и кэш LLM.

### Ключевые структуры

- **`CacheManager(cache_dir)`**
  - `index_path`, `llm_cache_path` — пути к `index.json` и `llm_cache.json`.
  - Методы:
    - `load_index()`, `save_index(data)` — работа с индексом файлов.
    - `load_llm_cache()`, `save_llm_cache(data)` — работа с кэшем LLM.
    - `diff_files(current_files)` — возвращает `(added, modified, deleted, unchanged)`.

---

## `tokens` — токенизация текста

Подсчёт и разбиение текста по токенам с использованием `tiktoken`.

### Основные функции

- **`get_encoding(model)`**  
  Возвращает кодировку для модели (например, `gpt-4`). Резерв — `cl100k_base`.

- **`count_tokens(text, model)`**  
  Возвращает количество токенов в тексте.

- **`chunk_text(text, model, max_tokens)`**  
  Разбивает текст на фрагменты, каждый ≤ `max_tokens`.

---

## `changes` — формирование отчётов об изменениях

Генерирует Markdown-отчёт о модифицированных файлах и перегенерированных разделах.

### Основные функции

- **`format_changes_md(added, modified, deleted, regenerated_sections, summary)`**  
  Возвращает строку в формате Markdown с детализацией изменений.

---

## `__main__` — запуск приложения

Точка входа при выполнении `python -m ai_docs`. Динамически загружает `main` из `cli`.

### Основные функции

- **`_load_main()`**  
  Импортирует `main` из `ai_docs.cli`, корректируя `sys.path` при необходимости.

- **`main()`**  
  Вызывает основную функцию CLI. Обрабатывает `ImportError` при проблемах с импортом.

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
