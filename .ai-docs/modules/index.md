# Модули

## `scanner` — сканирование исходных файлов

Модуль отвечает за рекурсивный анализ файловой структуры проекта (локального или удалённого) с фильтрацией по расширениям, размеру и правилам игнорирования. Результат — объект `ScanResult`, содержащий метаданные и содержимое подходящих файлов.

### Ключевые структуры

- **`ScanResult`** — результат сканирования:
  - `root: Path` — абсолютный путь к корню сканирования
  - `files: List[FileEntry]` — список обработанных файлов
  - `source: str` — исходный путь или URL
  - `repo_name: str` — имя репозитория

### Основные функции

- `scan_source(source: str, include=None, exclude=None, max_size=200000) -> ScanResult`  
  Сканирует директорию или клонирует репозиторий по URL. Применяет фильтры из `.ai-docs.yaml`, `.gitignore`, `.build_ignore`.  
  Исключения: `FileNotFoundError` при отсутствии локального пути.

- `_load_extension_config(root: Path) -> Dict[str, object]`  
  Загружает `.ai-docs.yaml` из корня проекта. Возвращает конфиг с полями:  
  `code_extensions`, `doc_extensions`, `config_extensions`, `exclude`.

- `_scan_directory(root, include, exclude, max_size) -> List[Dict]`  
  Рекурсивно обходит директорию. Возвращает список словарей с полями:  
  `path` (относительный), `abs_path`, `size`, `content`, `type`, `domains`.  
  Пропускает файлы при ошибках доступа (`OSError`).

- `_should_include(rel_path, include, exclude, ignore_specs) -> bool`  
  Проверяет, должен ли файл быть включён. Учитывает glob-шаблоны, `exclude` и `PathSpec` из `.gitignore`.

- `_clone_repo(repo_url) -> Tuple[Path, str]`  
  Клонирует репозиторий во временную директорию. Возвращает путь и имя репозитория.  
  Исключение: `RuntimeError` при ошибке клонирования.

---

## `cli` — точка входа и обработка аргументов

Модуль парсит командную строку, инициализирует сканирование и запускает генерацию документации.

### Основные функции

- `parse_args() -> argparse.Namespace`  
  Поддерживает аргументы:
  - `--source` — путь или URL (обязательный)
  - `--output` — директория вывода
  - `--readme`, `--mkdocs` — флаги генерации
  - `--language` — язык (`ru`/`en`)
  - `--include`, `--exclude` — фильтры
  - `--max-size` — лимит размера файла (байт)
  - `--cache-dir`, `--no-cache` — управление кэшем
  - `--threads` — параллельная обработка
  - `--local-site` — настройка MkDocs для локального запуска
  - `--force` — перезапись `README.md`

- `resolve_output(source, output, repo_name) -> Path`  
  Определяет путь вывода: если не задан — использует `./output/<repo_name>`.

- `main()`  
  Основная логика: сканирование → анализ → генерация → запись.  
  Исключения: ошибки доступа к LLM, файловой системе, сканированию.

---

## `llm` — взаимодействие с языковыми моделями

Клиент для отправки запросов к LLM с поддержкой кэширования и управления контекстом.

### Классы

- **`LLMClient`**  
  Поля:
  - `api_key`, `base_url`, `model`
  - `temperature`, `max_tokens`, `context_limit`  
  Методы:
  - `chat(messages: list[dict], cache: dict | None) -> str` — отправляет запрос, возвращает ответ.  
    Кэширует по хешу тела запроса (`_cache_key`).
  - `from_env() -> LLMClient` — создаёт клиент из переменных окружения.  
    Требует `OPENAI_API_KEY`.

---

## `summarizer` — генерация и нормализация описаний

Модуль генерирует и форматирует описания файлов с помощью LLM.

### Основные функции

- `summarize_file(content, file_type, domains, llm_client, llm_cache, model, detailed=False) -> str`  
  Разбивает содержимое на фрагменты (`chunk_text`), обрабатывает через `LLMClient`, объединяет результат.

- `_summarize_chunk(chunk, file_type, domains, llm_client, llm_cache, model) -> str`  
  Формирует промпт и запрашивает описание фрагмента.

- `_normalize_module_summary(summary, llm_client, llm_cache) -> str`  
  Приводит текст к Doxygen-стилю (удаляет Markdown, списки, заголовки).

- `_normalize_config_summary(summary, llm_client, llm_cache) -> str`  
  Нормализует описание конфигурационного файла в единый формат.

- `_strip_fenced_markdown(text) -> str`  
  Удаляет обрамляющие ``` из ответа LLM.

- `summarize_chunks(chunks, llm_client, llm_cache, detailed=False, file_type="module") -> str`  
  Объединяет несколько фрагментов в одно резюме.

- `write_summary(summary_dir, rel_path, summary) -> Path`  
  Сохраняет резюме в Markdown-файл с безопасным именем (через `safe_slug`).

---

## `docs_builder` — генерация документации MkDocs

Формирует структуру сайта MkDocs и сохраняет файлы.

### Основные функции

- `build_mkdocs_yaml(site_name, sections, configs, local_site=False, has_modules=False, module_nav_paths=None, project_config_nav_paths=None) -> str`  
  Генерирует `mkdocs.yml`. При `local_site=True` отключает `site_url` и `use_directory_urls`.

- `_build_tree_nav(paths, strip_prefix) -> List[Dict]`  
  Строит древовидную навигацию из списка путей. Использует `_insert_nav_node` и `_tree_to_nav`.

- `write_docs_files(docs_dir, files) -> None`  
  Записывает словарь `{относительный_путь: содержимое}` на диск, создавая директории при необходимости.

---

## `tokenizer` — подсчёт и разбиение токенов

Работает с `tiktoken` для управления длиной контекста.

### Функции

- `get_encoding(model: str)`  
  Возвращает кодировку модели. Резервная — `cl100k_base`.

- `count_tokens(text: str, model: str) -> int`  
  Подсчитывает токены в тексте.

- `chunk_text(text: str, model: str, max_tokens: int) -> List[str]`  
  Разбивает текст на фрагменты, укладываясь в лимит токенов.

---

## `utils` — вспомогательные функции

Набор утилит для работы с файлами, путями и данными.

### Функции

- `sha256_text(text: str) -> str`, `sha256_bytes(data: bytes) -> str` — хеширование.
- `read_text_file(path: Path) -> str` — чтение UTF-8 файла.
- `safe_slug(path: str) -> str` — преобразование строки в безопасное имя файла.
- `ensure_dir(path: Path)` — создание директории с родителями.
- `is_binary_file(path: Path, sample_size=2048) -> bool` — проверка на двоичный файл.
- `is_url(value: str) -> bool` — проверка строки на URL.
- `to_posix(path: Path) -> str` — преобразование пути в POSIX-формат.

---

## `classifier` — классификация файлов

Определяет тип и домены файлов.

### Функции

- `classify_type(path: Path) -> str`  
  Возвращает: `code`, `docs`, `config`, `data`, `ci`, `infra`, `other`.

- `detect_domains(path: Path, content_snippet: str) -> Set[str]`  
  Определяет домены: `kubernetes`, `docker`, `terraform`, `ci`, `helm` и др.

- `is_infra(domains: Set[str]) -> bool`  
  Проверяет, относится ли файл к инфраструктуре.

---

## `cache` — управление кэшем

Хранит индекс файлов и кэш LLM на диске.

### Классы

- **`CacheManager`**  
  Поля:
  - `cache_dir`, `index_path`, `llm_cache_path`  
  Методы:
  - `load_index() -> Dict`, `save_index(data)`
  - `load_llm_cache() -> Dict`, `save_llm_cache(data)`
  - `diff_files(current_files) -> (added, modified, deleted, unchanged)` — сравнение состояний.

---

## `changes` — формирование отчётов об изменениях

Генерирует Markdown-отчёт о модификациях.

### Функция

- `format_changes_md(added, modified, deleted, regenerated_sections, summary) -> str`  
  Возвращает отчёт с заголовками и маркированными списками.

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
