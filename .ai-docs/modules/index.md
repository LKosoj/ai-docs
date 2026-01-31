# Модули

## `scanner`

Модуль `scanner` предназначен для анализа исходного кода из локальной директории или удалённого Git-репозитория. Он рекурсивно сканирует файлы, применяет правила включения и исключения, определяет их тип и предметные области (домены), фильтрует бинарные и слишком большие файлы, а также учитывает `.gitignore` и другие ignore-файлы. Результат — структурированный объект `ScanResult` с информацией о каждом подходящем файле.

### Константы

```python
DEFAULT_INCLUDE_PATTERNS: Set[str]
```
Шаблоны файлов по умолчанию, включаемые в сканирование. Обычно включают исходный код, конфигурации и документацию (например, `*.py`, `*.yaml`, `README.md`).

```python
DEFAULT_EXCLUDE_PATTERNS: Set[str]
```
Шаблоны файлов по умолчанию, исключаемые из сканирования. Включают скрытые директории, виртуальные окружения, артефакты сборки (например, `.venv/`, `__pycache__/`, `*.log`).

### Класс `ScanResult`

Результат сканирования исходного кода.

**Поля:**
- `root` (`Path`) — абсолютный путь к корневой директории сканирования.
- `files` (`List[Dict]`) — список метаданных прошедших фильтрацию файлов. Каждый словарь содержит:
  - `path` — относительный путь к файлу.
  - `abs_path` — абсолютный путь.
  - `size` — размер в байтах.
  - `content` — содержимое файла (если текстовый и в пределах `max_size`).
  - `type` — тип файла (например, `code`, `config`).
  - `domains` — множество доменов (например, `kubernetes`, `docker`).
- `source` (`str`) — исходная строка (URL или путь), переданная в `scan_source`.
- `repo_name` (`str`) — имя репозитория (из URL или имени директории).

### Функции

#### `_load_ignore_specs(root: Path) -> List[pathspec.PathSpec]`

Загружает и компилирует правила игнорирования из `.gitignore` и `.build_ignore` в указанной директории.

**Аргументы:**
- `root` — корневая директория проекта.

**Возвращает:**
- Список скомпилированных `pathspec.PathSpec`, используемых для проверки путей.

#### `_should_include(rel_path: str, include: Optional[Set[str]], exclude: Optional[Set[str]], ignore_specs: List[pathspec.PathSpec]) -> bool`

Определяет, должен ли файл быть включён в результаты сканирования.

**Аргументы:**
- `rel_path` — относительный путь к файлу (в формате POSIX).
- `include` — пользовательские шаблоны включения. Если `None`, включаются все файлы, не исключённые другими правилами.
- `exclude` — пользовательские шаблоны исключения.
- `ignore_specs` — список скомпилированных спецификаций игнорирования.

**Возвращает:**
- `True`, если файл прошёл все фильтры; `False` — если должен быть пропущен.

#### `_scan_directory(root: Path, include: Optional[Set[str]], exclude: Optional[Set[str]], max_size: int) -> List[Dict]`

Рекурсивно сканирует директорию и возвращает список подходящих файлов.

**Аргументы:**
- `root` — корневая директория.
- `include` — шаблоны включения.
- `exclude` — шаблоны исключения.
- `max_size` — максимальный размер файла в байтах (файлы больше — пропускаются).

**Возвращает:**
- Список словарей с метаданными файлов, прошедших фильтрацию.

#### `_clone_repo(repo_url: str) -> Tuple[Path, str]`

Клонирует удалённый Git-репозиторий в временную директорию.

**Аргументы:**
- `repo_url` — URL репозитория (HTTP/HTTPS).

**Возвращает:**
- Кортеж: путь к временной директории и имя репозитория (без `.git`).

**Исключения:**
- `RuntimeError` — при ошибке клонирования (недоступный URL, сетевая ошибка и т.п.).

#### `scan_source(source: str, include: Optional[Set[str]] = None, exclude: Optional[Set[str]] = None, max_size: int = 200000) -> ScanResult`

Основная функция модуля. Сканирует локальную директорию или клонирует и сканирует удалённый репозиторий.

**Аргументы:**
- `source` — путь к локальной директории или URL Git-репозитория.
- `include` — пользовательские шаблоны включения (по умолчанию — `DEFAULT_INCLUDE_PATTERNS`).
- `exclude` — пользовательские шаблоны исключения (по умолчанию — `DEFAULT_EXCLUDE_PATTERNS`).
- `max_size` — максимальный размер файла в байтах (по умолчанию — 200 КБ).

**Возвращает:**
- Объект `ScanResult`.

**Исключения:**
- `FileNotFoundError` — если локальный путь не существует.
- `RuntimeError` — если не удалось клонировать репозиторий.

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
