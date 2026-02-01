# Модули

## `scanner` — сканирование исходных файлов

Модуль отвечает за рекурсивный анализ файловой структуры проекта (локального или удалённого), фильтрацию файлов по расширениям, размеру и правилам игнорирования. Результат — объект `ScanResult` с метаданными и содержимым подходящих файлов.

### Ключевые структуры
- `ScanResult` — результат сканирования: корневой путь, список файлов, источник, имя репозитория.
- `FileEntry` — запись о файле: путь, размер, содержимое, тип, домены.

### Основные функции
- `scan_source(source, include=None, exclude=None, max_size=200000)`  
  Сканирует локальную директорию или Git-репозиторий.  
  Автоматически загружает `.ai-docs.yaml` и `.gitignore`.  
  Возвращает `ScanResult`.  
  Исключения: `FileNotFoundError` (если путь не существует), `RuntimeError` (ошибка клонирования).

- `_load_extension_config(root: Path)`  
  Загружает `.ai-docs.yaml` из корня проекта. Возвращает конфиг с полями:  
  `code_extensions`, `doc_extensions`, `config_extensions`, `exclude`.

- `_load_ignore_specs(root: Path)`  
  Загружает и компилирует правила из `.gitignore` и `.build_ignore` в `pathspec.PathSpec`.

- `_should_include(rel_path, include, exclude, ignore_specs)`  
  Проверяет, должен ли файл быть включён. Учитывает glob-паттерны, исключения и `.gitignore`.

- `_scan_directory(root, include, exclude, max_size)`  
  Рекурсивно сканирует директорию. Возвращает список словарей с полями:  
  `path`, `abs_path`, `size`, `content`, `type`, `domains`.  
  Двоичные файлы и превышающие `max_size` пропускаются.

- `_clone_repo(repo_url)`  
  Клонирует репозиторий во временную директорию. Возвращает `(temp_path, repo_name)`.

---

## `llm` — взаимодействие с языковой моделью

Модуль предоставляет клиент для отправки запросов к LLM через OpenAI-совместимый API с поддержкой кэширования.

### Ключевые структуры
- `LLMClient` — клиент с настройками модели, температурой, лимитами токенов и кэшированием.

### Методы `LLMClient`
- `__init__(api_key, base_url, model, temperature=0.2, max_tokens=1200, context_limit=8192)`  
  Инициализирует клиент. `base_url` может включать `/v1`.

- `chat(messages, cache=None)`  
  Отправляет список сообщений вида `{"role": "user", "content": "..."}`.  
  Если передан `cache`, использует хеш тела запроса для повторного использования ответа.  
  Возвращает строку с ответом модели.  
  Исключение: `RuntimeError`, если ответ не содержит контента.

- `_cache_key(payload)`  
  Генерирует SHA256-хеш JSON-представления запроса.

- `from_env()`  
  Создаёт клиент на основе переменных окружения:  
  `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`.  
  Исключение: `RuntimeError`, если `OPENAI_API_KEY` не задан.

---

## `summarizer` — генерация и нормализация описаний

Модуль обрабатывает содержимое файлов, генерирует и форматирует аннотации с помощью LLM.

### Основные функции
- `summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False)`  
  Генерирует резюме файла. Типы: `config`, `infra`, `module`.  
  Использует кэш для ускорения. Возвращает Markdown.

- `_normalize_module_summary(summary, llm_client, llm_cache)`  
  Приводит описание модуля к Doxygen-формату (удаляет Markdown, списки, заголовки).

- `_normalize_config_summary(summary, llm_client, llm_cache)`  
  Нормализует описание конфигурации в единый структурированный вид.

- `_format_config_blocks(text)`  
  Форматирует секции конфигурации: объединяет строки через `<br>`, разделяет блоки пустыми строками.

- `_needs_doxygen_fix(text)`  
  Проверяет, содержит ли текст Markdown-элементы (списки, заголовки, код).

- `_strip_fenced_markdown(text)`  
  Удаляет обрамляющие ```` ```lang ``` ```` из текста.

- `chunk_text(content, model, max_tokens)`  
  Разбивает текст на части по токенам с использованием `tiktoken`.

- `write_summary(summary_dir, rel_path, summary)`  
  Сохраняет резюме в `summary_dir` с именем, производным от `rel_path`. Возвращает путь к файлу.

---

## `generator` — генерация документации

Модуль строит структуру документации, генерирует README и MkDocs-сайт.

### Ключевые структуры
- `DOMAIN_TITLES` — маппинг доменов (`kubernetes`, `docker`) в локализованные заголовки.
- `SECTION_TITLES` — стандартные названия секций (например, "Зависимости").

### Основные функции
- `_generate_readme(llm, llm_cache, project_name, overview_context, language)`  
  Генерирует `README.md` на основе контекста проекта.

- `_submit_section(path, title, context)`  
  Асинхронно отправляет задачу на генерацию секции.

- `_generate_section(llm, llm_cache, title, context, language)`  
  Генерирует одну секцию документации.

- `_render_project_configs_index(nav_paths)`  
  Формирует индекс страниц конфигураций в Markdown.

- `_collect_dependencies(file_map)`  
  Извлекает зависимости из карты файлов.

- `format_changes_md(added, modified, deleted, regenerated_sections, summary)`  
  Формирует отчёт об изменениях в Markdown.

- `_build_docs_index(output_root, docs_dir, docs_files, file_map, module_pages, config_pages)`  
  Строит JSON-индекс навигации.

---

## `writer` — запись и конфигурация документации

Модуль генерирует `mkdocs.yml` и записывает файлы на диск.

### Основные функции
- `build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None, project_config_nav_paths=None)`  
  Генерирует YAML-конфиг для MkDocs. При `local_site=True` отключает `site_url` и `use_directory_urls`.

- `_build_tree_nav(paths, strip_prefix)`  
  Строит древовидную навигацию из списка путей.

- `_insert_nav_node(tree, parts, rel_path)`  
  Рекурсивно вставляет узел в дерево по частям пути.

- `_tree_to_nav(tree)`  
  Преобразует внутреннее дерево в формат, пригодный для `mkdocs.yml`.

- `write_docs_files(docs_dir, files)`  
  Записывает все файлы из словаря `путь → содержимое` в `docs_dir`.  
  Исключения: `OSError` при ошибках записи.

---

## `utils` — вспомогательные функции

Набор утилит для работы с файлами, путями, хешированием и типами.

### Основные функции
- `sha256_bytes(data)` / `sha256_text(text)`  
  Возвращают SHA-256 хеш в hex-формате.

- `read_text_file(path)`  
  Читает файл в UTF-8. Исключение: `OSError`.

- `safe_slug(path)`  
  Заменяет все неалфавитно-цифровые символы на `_`.

- `ensure_dir(path)`  
  Создаёт директорию и все родительские. Исключение: `OSError`.

- `is_binary_file(path, sample_size=2048)`  
  Проверяет наличие нулевых байтов в первых `sample_size` байтах. При ошибках чтения возвращает `True`.

- `is_url(value)`  
  Проверяет, начинается ли строка с `http://`, `https://` или `git@`.

- `to_posix(path)`  
  Преобразует `Path` в строку с `/`, независимо от ОС.

---

## `classifier` — классификация файлов

Определяет тип файла и домены инфраструктуры.

### Функции
- `classify_type(path)`  
  Возвращает: `code`, `docs`, `config`, `data`, `ci`, `infra`, `other`.

- `detect_domains(path, content_snippet)`  
  Возвращает множество доменов: `kubernetes`, `docker`, `terraform`, `ci`, `helm`, `auth`, `billing` и др.

- `is_infra(domains)`  
  Проверяет, содержит ли множество доменов инфраструктурные (`kubernetes`, `docker`, `terraform`, `ci`, `helm`).

---

## `tokenizer` — подсчёт и разбиение токенов

Работает с `tiktoken` для оценки длины текста в токенах.

### Функции
- `get_encoding(model)`  
  Возвращает кодировку для модели. Резервная — `cl100k_base`.

- `count_tokens(text, model)`  
  Возвращает количество токенов в тексте.

- `chunk_text(text, model, max_tokens)`  
  Разбивает текст на части по `max_tokens`.

---

## `cache` — управление кэшем

Хранит индекс файлов и кэш LLM-ответов в JSON-файлах.

### Класс `CacheManager`
- Поля: `cache_dir`, `index_path`, `llm_cache_path`.
- Методы:
  - `load_index()` — загружает `index.json`, возвращает словарь.
  - `save_index(data)` — сохраняет индекс.
  - `load_llm_cache()` — загружает `llm_cache.json`.
  - `save_llm_cache(data)` — сохраняет кэш LLM.
  - `diff_files(current_files)` — сравнивает текущие файлы с кэшированными. Возвращает кортеж: `(added, modified, deleted, unchanged)`.

---

## `main` — точка входа CLI

Запускает полный цикл: парсинг аргументов, сканирование, генерация, запись.

### Функции
- `parse_args()`  
  Парсит аргументы командной строки: `--source`, `--output`, `--readme`, `--mkdocs`, `--language`, `--max-size`, `--cache-dir`, `--threads` и др.

- `resolve_output(source, output, repo_name)`  
  Определяет путь вывода. Если не задан — использует `./output/<repo_name>`.

- `main()`  
  Основная логика: сканирование, генерация, запись.  
  Исключения: ошибки сканирования, LLM, записи файлов.

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
