# Модули

Проект структурирован в виде набора модулей, каждый из которых отвечает за определённую часть функциональности: от сканирования исходных файлов до генерации итоговой документации. Ниже приведено описание ключевых модулей и их интерфейсов.

---

## `scanner`

Модуль отвечает за сканирование файлов в локальной директории или удалённом репозитории. Формирует объект `ScanResult` с метаданными и содержимым файлов, подходящих под фильтры.

### Основные функции

- **`scan_source(source: str, include: Set[str] = None, exclude: Set[str] = None, max_size: int = 200000) -> ScanResult`**  
  Сканирует указанный путь или URL репозитория.  
  - `source`: путь к директории или Git-URL.  
  - `include`: шаблоны включения (glob), если `None` — используются настройки из `.ai-docs.yaml`.  
  - `exclude`: шаблоны исключения, дополняются правилами из `.gitignore` и `.build_ignore`.  
  - `max_size`: максимальный размер файла в байтах (по умолчанию 200 КБ).  
  - Возвращает `ScanResult` с корневым путём, списком файлов, источником и именем репозитория.  
  - Исключение: `FileNotFoundError`, если локальный путь не существует.

- **`_load_extension_config(root: Path) -> Dict[str, object]`**  
  Загружает `.ai-docs.yaml` из корня проекта. Возвращает словарь с полями:  
  - `code_extensions`, `doc_extensions`, `config_extensions` — расширения по типам.  
  - `exclude` — шаблоны исключения.  
  Если файла нет — возвращает значения по умолчанию.

- **`_should_include(rel_path: str, include: Set[str], exclude: Set[str], ignore_specs: List[PathSpec]) -> bool`**  
  Проверяет, должен ли файл быть включён в результат. Учитывает:  
  - шаблоны `include` и `exclude`,  
  - правила из `.gitignore` и `.build_ignore`.  
  Возвращает `True`, если файл проходит фильтрацию.

---

## `cli`

Точка входа приложения. Парсит аргументы командной строки и запускает основной процесс генерации документации.

### Основные функции

- **`parse_args() -> argparse.Namespace`**  
  Обрабатывает аргументы:  
  - `--source` — обязательный путь или URL.  
  - `--output` — директория вывода (по умолчанию `./output/<repo>`).  
  - `--readme`, `--mkdocs` — флаги генерации.  
  - `--language` — язык (`ru` или `en`).  
  - `--max-size`, `--threads`, `--cache-dir`, `--force` — дополнительные настройки.  
  Возвращает объект с распарсенными параметрами.

- **`resolve_output(source: str, output: str, repo_name: str) -> Path`**  
  Определяет итоговую директорию вывода. Если `output` не задан — формирует путь на основе имени репозитория.

- **`main()`**  
  Основная логика:  
  1. Парсит аргументы.  
  2. Сканирует исходники.  
  3. Инициализирует `LLMClient`.  
  4. Запускает `generate_docs`.  
  При ошибках — выводит сообщение и завершается с кодом 1.

---

## `llm`

Работа с языковыми моделями через API, совместимое с OpenAI. Поддерживает кэширование и управление контекстом.

### Класс `LLMClient`

- **Поля**:  
  `api_key`, `base_url`, `model`, `temperature`, `max_tokens`, `context_limit`.

- **Методы**:  
  - `__init__()` — инициализация клиента.  
  - `chat(messages: list[dict], cache: dict = None) -> str` — отправляет запрос к модели. Если `cache` задан и содержит хеш тела — возвращает закэшированный ответ.  
  - `_cache_key(payload: dict) -> str` — генерирует SHA256-хеш от JSON-представления запроса.  
  - `from_env()` — создаёт клиент из переменных окружения (`OPENAI_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`).

---

## `processor`

Обработка файлов и генерация кратких описаний с помощью LLM.

### Основные функции

- **`summarize_file(content: str, file_type: str, domains: List[str], llm_client, llm_cache, model: str, detailed: bool = False) -> str`**  
  Генерирует описание содержимого файла.  
  - `detailed=True` — формат Doxygen.  
  - `domains` — используются для контекста (например, "kubernetes").  
  Результат кэшируется по хешу входных данных.

- **`_normalize_module_summary(summary: str, llm_client, llm_cache) -> str`**  
  Приводит текст к строгому Doxygen-формату, если `_needs_doxygen_fix()` возвращает `True`.

- **`write_summary(summary_dir: Path, rel_path: str, summary: str) -> Path`**  
  Сохраняет резюме в подкаталоге `summary_dir`, сохраняя структуру путей. Создаёт промежуточные директории.

---

## `docs`

Генерация структуры документации и конфигурации MkDocs.

### Основные функции

- **`build_mkdocs_yaml(site_name: str, sections: Dict[str, str], configs: Dict[str, str], local_site: bool, has_modules: bool, module_nav_paths: List[str]) -> str`**  
  Формирует содержимое `mkdocs.yml`.  
  - `sections` — основные разделы (архитектура, запуск и т.д.).  
  - `configs` — файлы конфигурации.  
  - `module_nav_paths` — пути к страницам модулей для построения навигации.

- **`_build_modules_nav(module_paths: List[str]) -> List[Dict]`**  
  Строит иерархическую навигацию по модулям. Использует вспомогательные функции:  
  - `_insert_nav_node()` — рекурсивно добавляет узел в дерево.  
  - `_tree_to_nav()` — преобразует дерево в формат MkDocs.

- **`write_docs_files(docs_dir: Path, files: Dict[str, str])`**  
  Записывает все файлы документации, создавая недостающие директории.

---

## `generator`

Основной модуль генерации документации. Собирает контекст, вызывает LLM и формирует итоговые файлы.

### Основные функции

- **`generate_docs(files: List[Dict], output_root: Path, cache_dir: Path, llm: LLMClient, language: str, write_readme: bool, write_mkdocs: bool, use_cache: bool, threads: int, local_site: bool, force: bool)`**  
  Полный цикл генерации:  
  1. Загружает кэш.  
  2. Определяет изменения (через `CacheManager.diff_files`).  
  3. Параллельно обрабатывает файлы (если `threads > 1`).  
  4. Генерирует разделы: зависимости, тесты, архитектура.  
  5. Сохраняет `README.md` и `mkdocs.yml`.  
  6. Обновляет кэш.

- **`_generate_section(llm, llm_cache, title, context, language) -> str`**  
  Запрашивает у LLM содержимое одного раздела. Удаляет дублирующий заголовок через `_strip_duplicate_heading()`.

- **`_truncate_context(context: str, model: str, max_tokens: int) -> str`**  
  Обрезает текст, чтобы уложиться в лимит токенов (с помощью `token_counter.chunk_text`).

---

## `utils`

Вспомогательные функции для работы с файлами, путями и данными.

### Основные функции

- **`sha256_text(text: str) -> str`**, **`sha256_bytes(data: bytes) -> str`** — вычисление хешей.
- **`read_text_file(path: Path) -> str`** — безопасное чтение UTF-8 файла.
- **`ensure_dir(path: Path)`** — создание директории с родителями.
- **`is_binary_file(path: Path, sample_size: int = 2048) -> bool`** — проверка на бинарный файл по наличию `\x00`.
- **`to_posix(path: Path) -> str`** — преобразование пути в POSIX-формат (`/` вместо `\`).
- **`is_url(value: str) -> bool`** — проверка, является ли строка URL (`http://`, `https://`, `git@`).

---

## `classifier`

Классификация файлов по типу и доменам инфраструктуры.

### Основные функции

- **`classify_type(path: Path) -> str`**  
  Возвращает тип: `code`, `docs`, `config`, `infra`, `ci`, `data`, `other`.  
  Определяется по расширению или имени файла (например, `Dockerfile` → `infra`).

- **`detect_domains(path: Path, content_snippet: str) -> Set[str]`**  
  Определяет домены: `kubernetes`, `docker`, `terraform`, `ci`, `aws` и др.  
  Анализирует путь и первые 512 символов содержимого.

- **`is_infra(domains: Set[str]) -> bool`**  
  Проверяет, содержит ли множество доменов инфраструктурные компоненты.

---

## `cache`

Управление кэшем промежуточных данных и ответов LLM.

### Класс `CacheManager`

- **Поля**:  
  `cache_dir`, `index_path`, `llm_cache_path`.

- **Методы**:  
  - `load_index()`, `save_index(data)` — работа с `index.json`.  
  - `load_llm_cache()`, `save_llm_cache(data)` — работа с `llm_cache.json`.  
  - `diff_files(current_files) -> (added, modified, deleted, unchanged)` — сравнение по хешам содержимого.

---

## `token_counter`

Подсчёт и разбиение текста на токены.

### Основные функции

- **`get_encoding(model: str)`**  
  Возвращает кодировку `tiktoken` для модели. Резервная — `cl100k_base`.

- **`count_tokens(text: str, model: str) -> int`**  
  Возвращает количество токенов в тексте.

- **`chunk_text(text: str, model: str, max_tokens: int) -> List[str]`**  
  Разбивает текст на фрагменты, каждый ≤ `max_tokens`. Используется при обработке больших файлов.

---

## `changes`

Формирование отчёта об изменениях в Markdown.

### Основная функция

- **`format_changes_md(added, modified, deleted, regenerated_sections, summary) -> str`**  
  Возвращает строку в формате Markdown с:  
  - списками изменённых файлов,  
  - перечнем перегенерированных разделов,  
  - кратким резюме.  
  Используется для логирования изменений при генерации.

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
