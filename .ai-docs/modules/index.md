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

- **`scan_source(source, include=None, exclude=None, max_size=200000)`**  
  Сканирует локальную директорию или клонирует Git-репозиторий.  
  Применяет фильтры по расширениям, `.gitignore`, `.build_ignore` и максимальному размеру файла.  
  Возвращает `ScanResult`.  
  Исключения: `FileNotFoundError` (если путь не существует), `RuntimeError` (ошибка клонирования).

- **`_load_extension_config(root)`**  
  Загружает `.ai-docs.yaml` из корня проекта. Возвращает конфиг с полями:
  - `code_extensions`, `doc_extensions`, `config_extensions` — расширения по типам.
  - `exclude` — шаблоны исключения.

- **`_load_ignore_specs(root)`**  
  Загружает и компилирует правила из `.gitignore` и `.build_ignore` в `pathspec.PathSpec`.

- **`_should_include(rel_path, include, exclude, ignore_specs)`**  
  Проверяет, должен ли файл быть включён. Учитывает:
  - `include` — glob-паттерны включения.
  - `exclude` — glob-паттерны исключения.
  - `ignore_specs` — правила из `.gitignore`.

- **`_scan_directory(root, include, exclude, max_size)`**  
  Рекурсивно обходит директорию, читает содержимое текстовых файлов.  
  Возвращает список словарей с полями: `path`, `abs_path`, `size`, `content`, `type`, `domains`.  
  Двоичные файлы пропускаются.

---

## `llm` — взаимодействие с языковыми моделями

Модуль предоставляет клиент для отправки запросов к LLM через OpenAI-совместимый API с поддержкой кэширования.

### Ключевые структуры

- **`LLMClient`** — клиент для работы с LLM:
  - `api_key`, `base_url`, `model` — параметры подключения.
  - `temperature`, `max_tokens`, `context_limit` — настройки генерации.
  - Метод `chat(messages, cache=None)` — отправляет запрос, возвращает текст ответа.
  - `_cache_key(payload)` — генерирует SHA256-хеш тела запроса для кэширования.
  - `from_env()` — создаёт клиент из переменных окружения (`OPENAI_API_KEY`, `LLM_MODEL` и др.).

---

## `summarizer` — генерация и нормализация описаний

Модуль обрабатывает содержимое файлов, генерирует и форматирует резюме с помощью LLM.

### Основные функции

- **`summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False)`**  
  Генерирует Markdown-резюме файла. Типы: `code`, `config`, `infra`.  
  Использует кэширование по хешу контекста.

- **`_normalize_module_summary(summary, llm_client, llm_cache)`**  
  Приводит описание модуля к Doxygen-формату (удаляет Markdown, списки, заголовки).

- **`_normalize_config_summary(summary, llm_client, llm_cache)`**  
  Нормализует описание конфигурации в единый структурированный вид.

- **`_strip_fenced_markdown(text)`**  
  Удаляет обрамляющие ```` ```lang ``` ```` из текста.

- **`_needs_doxygen_fix(text)`**  
  Проверяет, содержит ли текст Markdown-элементы, требующие очистки.

- **`chunk_text(content, model, max_tokens)`**  
  Разбивает текст на части по токенам (с использованием `tiktoken`).

- **`write_summary(summary_dir, rel_path, summary)`**  
  Сохраняет резюме в `summary_dir` с путём, соответствующим `rel_path`.

---

## `docs_builder` — генерация документации

Модуль формирует структуру документации, генерирует `mkdocs.yml`, записывает файлы.

### Основные функции

- **`build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None, project_config_nav_paths=None)`**  
  Генерирует YAML-конфигурацию MkDocs с навигацией и настройками.

- **`_build_tree_nav(paths, strip_prefix)`**  
  Строит иерархическую навигацию из списка путей (например, `src/api/server.py` → вложенность).

- **`_insert_nav_node(tree, parts, rel_path)`**, **`_tree_to_nav(tree)`**  
  Вспомогательные функции для построения дерева навигации.

- **`write_docs_files(docs_dir, files)`**  
  Записывает все файлы из словаря `path: content` в `docs_dir`.  
  Исключения: `PermissionError`, `IsADirectoryError` и др.

---

## `tokenizer` — подсчёт и разбиение токенов

Модуль работает с токенизацией текста для совместимости с LLM.

### Основные функции

- **`get_encoding(model)`**  
  Возвращает `tiktoken`-кодировку для модели. Резерв: `cl100k_base`.

- **`count_tokens(text, model)`**  
  Возвращает количество токенов в тексте.

- **`chunk_text(text, model, max_tokens)`**  
  Разбивает текст на части, не превышающие `max_tokens`.

---

## `utils` — вспомогательные утилиты

Набор функций для работы с файлами, путями и данными.

### Основные функции

- **`sha256_text(text)`**, **`sha256_bytes(data)`** — вычисление SHA-256.
- **`read_text_file(path)`** — безопасное чтение UTF-8 файла.
- **`ensure_dir(path)`** — создание директории с родителями.
- **`is_binary_file(path, sample_size=2048)`** — проверка на двоичный файл.
- **`is_url(value)`** — проверка строки на URL (`http://`, `https://`, `git@`).
- **`to_posix(path)`** — преобразование пути в POSIX-формат (`/`).
- **`safe_slug(path)`** — преобразование строки в безопасный слаг (замена спецсимволов на `_`).

---

## `classifier` — классификация файлов

Определяет тип и домены файлов для корректной обработки.

### Основные функции

- **`classify_type(path)`**  
  Возвращает тип: `code`, `config`, `docs`, `infra`, `ci`, `data`, `other`.

- **`detect_domains(path, content_snippet)`**  
  Определяет домены по имени, пути и фрагменту содержимого: `kubernetes`, `docker`, `terraform`, `ci`, `aws` и др.

- **`is_infra(domains)`**  
  Проверяет, относится ли файл к инфраструктурным доменам.

---

## `cache` — управление кэшем

Модуль хранит и сравнивает состояние файлов и кэш LLM.

### Ключевая структура

- **`CacheManager(cache_dir)`**:
  - `load_index()` / `save_index(data)` — работа с `index.json`.
  - `load_llm_cache()` / `save_llm_cache(data)` — работа с `llm_cache.json`.
  - `diff_files(current_files)` — возвращает `(added, modified, deleted, unchanged)` по сравнению с предыдущим индексом.

---

## `cli` — точка входа

Запускает приложение: парсит аргументы, сканирует исходники, генерирует документацию.

### Основные функции

- **`parse_args()`**  
  Обрабатывает CLI-аргументы: `--source`, `--output`, `--readme`, `--mkdocs`, `--language`, `--max-size`, `--cache-dir`, `--threads` и др.

- **`resolve_output(source, output, repo_name)`**  
  Определяет путь вывода: если не задан — использует `./output/<repo_name>`.

- **`main()`**  
  Основной поток:
  1. Парсинг аргументов.
  2. Сканирование исходников.
  3. Инициализация LLM и кэша.
  4. Генерация README и/или MkDocs.
  5. Запись файлов и отчёт об изменениях.

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
