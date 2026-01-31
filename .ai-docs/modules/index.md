# Модули

# Модуль `scanner` — Анализ исходного кода

Модуль `scanner` предназначен для рекурсивного анализа файлов в локальной директории или удалённом Git-репозитории. Он фильтрует файлы по правилам включения/исключения, учитывает `.gitignore`, определяет тип и домены файлов, пропускает бинарные и слишком большие файлы, и возвращает структурированные метаданные. Основное назначение — подготовка данных для последующей генерации документации.

## Конфигурация по умолчанию

```python
DEFAULT_INCLUDE_PATTERNS: Set[str]
```
Шаблоны файлов, включаемых по умолчанию:  
`*.py`, `*.js`, `*.ts`, `*.go`, `*.yaml`, `*.yml`, `*.json`, `*.md`, `*.rst`, `*.txt`, `Dockerfile`, `Makefile`, `*.tf`, `*.tpl`.

```python
DEFAULT_EXCLUDE_PATTERNS: Set[str]
```
Шаблоны, исключаемые по умолчанию:  
`.git/`, `__pycache__/`, `*.pyc`, `*.pyo`, `*.egg-info/`, `.venv/`, `venv/`, `node_modules/`, `*.log`, `*.tmp`, `*.swp`.

## Основные компоненты

### `ScanResult`
Результат сканирования — итоговая структура с метаданными.

**Поля:**
- `root`: `Path` — абсолютный путь к корню сканирования.
- `files`: `List[Dict]` — список файлов с полями:
  - `path`: относительный путь (POSIX).
  - `abs_path`: абсолютный путь.
  - `size`: размер в байтах.
  - `content`: содержимое файла (если текстовый и в пределах `max_size`).
  - `type`: тип файла (`code`, `docs`, `config`, `infra`, `ci`, `data`, `other`).
  - `domains`: набор доменов (`docker`, `kubernetes`, `terraform`, `helm`, `ansible` и др.).
- `source`: исходная строка (URL или путь).
- `repo_name`: имя репозитория (из URL или директории).

---

### `scan_source(source, include=None, exclude=None, max_size=200000)`
Основная функция модуля. Сканирует локальную директорию или клонирует удалённый репозиторий.

**Аргументы:**
- `source`: `str` — путь к директории или URL Git-репозитория.
- `include`: `Set[str]` — пользовательские шаблоны включения (по умолчанию `DEFAULT_INCLUDE_PATTERNS`).
- `exclude`: `Set[str]` — пользовательские шаблоны исключения (по умолчанию `DEFAULT_EXCLUDE_PATTERNS`).
- `max_size`: `int` — максимальный размер файла в байтах (по умолчанию 200 КБ).

**Возвращает:**
- `ScanResult` — структурированный результат сканирования.

**Исключения:**
- `FileNotFoundError` — если локальный путь не существует.
- `RuntimeError` — при ошибке клонирования репозитория.

---

### `_clone_repo(repo_url)`
Клонирует Git-репозиторий в временную директорию.

**Аргументы:**
- `repo_url`: `str` — URL репозитория (HTTP/HTTPS).

**Возвращает:**
- `Tuple[Path, str]` — путь к временной директории и имя репозитория (без `.git`).

**Исключения:**
- `RuntimeError` — при сбое клонирования.

---

### `_scan_directory(root, include, exclude, max_size)`
Рекурсивно сканирует директорию и возвращает список подходящих файлов.

**Аргументы:**
- `root`: `Path` — корневая директория.
- `include`, `exclude`: `Set[str]` — шаблоны включения/исключения.
- `max_size`: `int` — лимит размера файла.

**Возвращает:**
- `List[Dict]` — список файлов с метаданными.

**Фильтрация включает:**
- Пропуск бинарных файлов (`is_binary_file`).
- Проверку размера.
- Учёт `.gitignore` и `.build_ignore` через `_load_ignore_specs`.
- Применение правил включения/исключения через `_should_include`.

---

### `_load_ignore_specs(root)`
Загружает и компилирует правила игнорирования из `.gitignore` и `.build_ignore`.

**Аргументы:**
- `root`: `Path` — корневая директория.

**Возвращает:**
- `List[pathspec.PathSpec]` — список скомпилированных спецификаций.

---

### `_should_include(rel_path, include, exclude, ignore_specs)`
Определяет, должен ли файл быть включён.

**Аргументы:**
- `rel_path`: `str` — относительный путь (POSIX).
- `include`, `exclude`: `Set[str]` — пользовательские шаблоны.
- `ignore_specs`: `List[pathspec.PathSpec]` — правила из ignore-файлов.

**Логика:**
1. Если `include` задан — файл должен соответствовать хотя бы одному шаблону.
2. Если `exclude` задан — файл не должен соответствовать ни одному шаблону.
3. Файл не должен соответствовать ни одному правилу из `ignore_specs`.

**Возвращает:**
- `True`, если файл прошёл все проверки.

## Интеграция с другими модулями

- **`classify_type`** и **`detect_domains`** — определяют тип и домены файла.
- **`is_binary_file`** — проверяет, является ли файл бинарным.
- **`to_posix`** — нормализует пути к единому формату.
- **`read_text_file`** — безопасно читает содержимое файла в UTF-8.

## Практическое использование

```python
from scanner import scan_source

# Сканирование локальной директории
result = scan_source("./my-project")

# Сканирование удалённого репозитория
result = scan_source("https://github.com/user/repo.git")

# С пользовательскими фильтрами
result = scan_source(
    "./project",
    include={"*.py", "*.md"},
    exclude={"tests/", "*.pyc"},
    max_size=500000
)

# Доступ к результатам
for file in result.files:
    print(f"{file['path']} ({file['type']}, {file['size']} B)")
```

## Особенности
- Поддержка Git и `.gitignore` без зависимостей от `git` CLI.
- Автоматическое определение типа и доменов файлов.
- Безопасное чтение файлов (обработка `UnicodeDecodeError`).
- Временные директории для клонирования удаляются автоматически.
- Работает с большими репозиториями с фильтрацией на лету.

## Список модулей

- [modules/ai_docs/__init__](ai_docs/__init__.md)
- [modules/ai_docs/__main__](ai_docs/__main__.md)
- [modules/ai_docs/cache](ai_docs/cache.md)
- [modules/ai_docs/changes](ai_docs/changes.md)
- [modules/ai_docs/cli](ai_docs/cli.md)
- [modules/ai_docs/domain](ai_docs/domain.md)
- [modules/ai_docs/generator](ai_docs/generator.md)
- [modules/ai_docs/llm](ai_docs/llm.md)
- [modules/ai_docs/mkdocs](ai_docs/mkdocs.md)
- [modules/ai_docs/scanner](ai_docs/scanner.md)
- [modules/ai_docs/summary](ai_docs/summary.md)
- [modules/ai_docs/tokenizer](ai_docs/tokenizer.md)
- [modules/ai_docs/utils](ai_docs/utils.md)
- [modules/tests/__init__](tests/__init__.md)
- [modules/tests/test_cache](tests/test_cache.md)
- [modules/tests/test_changes](tests/test_changes.md)
- [modules/tests/test_scanner](tests/test_scanner.md)
