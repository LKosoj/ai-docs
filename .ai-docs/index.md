# Документация проекта

## Обзор

`ai_docs` — это CLI-инструмент для автоматической генерации и поддержки технической документации на основе анализа исходного кода, конфигураций и структуры проекта. Инструмент поддерживает локальные директории и Git-репозитории (локальные и удалённые), автоматически распознаёт технологические домены (Kubernetes, Terraform, Docker и др.) и генерирует документацию в формате `README.md` и полноценного сайта на базе **MkDocs**.

Основная цель — минимизация ручного труда при создании и поддержке документации за счёт LLM-обработки и инкрементального обновления.

---

## Установка и запуск

### Установка
```bash
pip install ai-docs-gen
```

Или из исходников:
```bash
git clone https://github.com/your-repo/ai_docs.git
cd ai_docs
pip install -e .
```

### Быстрый старт
```bash
ai-docs --source ./my-project --readme --mkdocs --language ru
```

---

## Конфигурация

### Переменные окружения
| Переменная | Назначение | По умолчанию |
|-----------|------------|--------------|
| `OPENAI_API_KEY` | Ключ для доступа к LLM | Обязательна |
| `OPENAI_BASE_URL` | Базовый URL API (поддержка OpenAI-совместимых эндпоинтов) | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Модель для генерации | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Температура генерации | `0.2` |
| `OPENAI_MAX_TOKENS` | Макс. токенов в ответе | `1200` |
| `AI_DOCS_THREADS` | Количество потоков обработки | `4` |
| `AI_DOCS_LOCAL_SITE` | Локальная сборка без публикации | `false` |

### Конфигурационный файл `.ai-docs.yaml`
Располагается в корне проекта. Позволяет кастомизировать:

```yaml
code_extensions:
  - ".py"
  - ".go"
  - ".ts"
doc_extensions:
  - ".md"
  - ".rst"
config_extensions:
  - ".yaml"
  - ".tf"
  - ".json"
exclude:
  - "temp/"
  - "*.log"
```

При отсутствии файла создаётся конфиг по умолчанию.

---

## Режимы работы

### Генерация README
```bash
ai-docs --source ./project --readme
```
Создаёт `README.md` в корне проекта. Перезаписывает, если указан `--force`.

### Генерация MkDocs-сайта
```bash
ai-docs --source ./project --mkdocs
```
Генерирует:
- `mkdocs.yml`
- Документацию в `.ai-docs/`
- Сайт в `ai_docs_site/`

Автоматически запускается `mkdocs build`.

### Локальная сборка (без публикации)
```bash
ai-docs --source ./project --mkdocs --local-site
```
Настройки в `mkdocs.yml` адаптируются под локальный запуск (относительные пути, отключённые плагины публикации).

---

## Фильтрация файлов

### Включение
- Автоматически включаются:
  - `Dockerfile`, `docker-compose.yml`
  - `*.tf`, `*.tfvars`
  - `k8s/*.yaml`, `helm/*.yaml`
  - `package.json`, `pyproject.toml`, `requirements.txt`
  - `*.lock`, `*.yaml`, `*.yml`
- Дополнительные расширения — через `.ai-docs.yaml`.

### Исключение
- По умолчанию исключаются:
  - `.git`, `.venv`, `__pycache__`, `node_modules`, `dist`, `build`, `.ai-docs`, `.ai_docs_cache`
- Учитываются `.gitignore` и `.build_ignore`
- Кастомные правила — через `exclude` в `.ai-docs.yaml`

### Ограничения
- Максимальный размер файла: **200 КБ** (настраивается через `--max-size`)
- Бинарные файлы (с нулевыми байтами) пропускаются

---

## Кэширование и производительность

### Кэш-директория: `.ai_docs_cache/`
- Хранит:
  - Хэши файлов (`index.json`)
  - Ответы LLM (`llm_cache.json`)
- Используется для инкрементальной обработки

### Управление кэшем
| Флаг | Действие |
|------|--------|
| `--no-cache` | Отключает кэширование LLM-запросов |
| `--force` | Принудительная перегенерация (игнорирует кэш) |

### Параллельная обработка
- Количество потоков: `AI_DOCS_THREADS` или `--threads N`
- Максимум 4 потока для генерации секций (ограничение по нагрузке)

---

## Структура выходных данных

```
project/
├── README.md                     # Краткий обзор
├── .ai-docs/                     # Исходники документации
│   ├── index.md                  # Главная страница
│   ├── architecture.md
│   ├── testing.md
│   ├── dependencies.md
│   ├── modules/                  # Описания модулей
│   ├── configs/                  # Конфигурационные файлы
│   └── _index.json               # Навигационный индекс
├── mkdocs.yml                    # Конфиг MkDocs
├── ai_docs_site/                 # Собранный сайт
└── changes.md                    # Отчёт об изменениях
```

---

## Поддерживаемые домены

Автоматическое распознавание:
- **Kubernetes / Helm**
- **Terraform / IaC**
- **Docker / Docker Compose**
- **CI/CD** (GitHub Actions, GitLab CI, Jenkins)
- **Ansible**
- **Observability** (Prometheus, Grafana)
- **Service Mesh / Ingress** (Istio, Traefik)
- **Data / Storage** (PostgreSQL, Redis, MinIO)

---

## Интеграция с MkDocs

### Генерация `mkdocs.yml`
Формируется автоматически с поддержкой:
- Навигации по секциям
- Автогенерации путей (`project_config_nav_paths`, `module_nav_paths`)
- Mermaid-диаграмм через `pymdownx.superfences`
- Кастомных JS/CSS (для визуализаций)

### Поддерживаемые плагины
- `mkdocs-mermaid2-plugin`
- `pymdown-extensions`

---

## Работа с LLM

### Клиент `LLMClient`
- Отправка запросов к OpenAI-совместимым API
- Кэширование по SHA256 от payload
- Потокобезопасность (через `threading.Lock`)
- Таймауты: 120 сек (connect), 480 сек (read)

### Промпты
- `SUMMARY_PROMPT` — общее резюме файла
- `MODULE_SUMMARY_PROMPT` — описание модуля
- `CONFIG_SUMMARY_PROMPT` — описание конфигурации
- Реформатирующие промпты — для нормализации вывода

### Нормализация
- Удаление недопустимых элементов (Doxygen-теги)
- Форматирование блоков конфигураций с `<br>`
- Объединение чанков через `chunk_text`

---

## Разработка и вклад

### Запуск для отладки
```bash
python -m ai_docs --source ./test-project --readme --no-cache
```

### Тестирование
```bash
pytest tests/test_scanner.py
pytest tests/test_cache.py
pytest tests/test_changes.py
```

### Требования
- Python ≥ 3.8
- Зависимости: `requests`, `tiktoken`, `PyYAML`, `python-dotenv`, `mkdocs`, `pathspec`

### Лицензия
MIT

---

## Использование в CI/CD

Пример для GitHub Actions:
```yaml
- name: Generate Docs
  run: |
    pip install ai-docs-gen
    ai-docs --source . --mkdocs --local-site
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## Ограничения
- Не обрабатывает бинарные файлы
- Ограничен размер файла (200 КБ)
- Требует стабильного интернета при работе с облачными LLM
- Не поддерживает частные модели без OpenAI-совместимого API

---

## Поддержка

- GitHub Issues: https://github.com/your-repo/ai_docs/issues
- PR приветствуются
- Документация обновляется автоматически при каждом запуске `ai-docs`
