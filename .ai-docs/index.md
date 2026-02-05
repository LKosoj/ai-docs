# Документация проекта

## Структура выходных артефактов

После выполнения `ai_docs` в корне проекта создаются следующие артефакты:

```
.
├── README.md                     # Краткое описание проекта
├── mkdocs.yml                    # Конфигурация сайта документации
├── ai_docs_site/                 # Собранный сайт (при включённой опции)
├── .ai-docs/                     # Детализированная документация
│   ├── index.md                  # Главная страница документации
│   ├── architecture.md           # Описание архитектуры (с Mermaid-диаграммами)
│   ├── modules/                  # Документация по модулям
│   │   ├── module_name.md        # Описание отдельного модуля
│   ├── configs/                  # Документация по конфигурациям
│   │   ├── config_name.md        # Описание конфигурационного файла
│   ├── testing.md                # Инструкции по запуску тестов
│   ├── dependencies.md           # Список зависимостей
│   ├── changes.md                # Отчёт об изменениях при генерации
│   └── _index.json               # Навигационный индекс (метаданные)
└── .ai_docs_cache/               # Кэш промежуточных данных
    ├── index.json                # Хэши и метаданные файлов
    ├── llm_cache.json            # Кэш ответов LLM
    ├── files/                    # Промежуточные резюме файлов
    ├── modules/                  # Резюме модулей
    └── configs/                  # Резюме конфигураций
```

---

## Генерация документации

### Базовый запуск
```bash
ai-docs --source /path/to/project
```
Сгенерирует `README.md` и MkDocs-сайт в `ai_docs_site/`.

### Указание удалённого репозитория
```bash
ai-docs --source https://github.com/user/repo.git
```

### Язык и фильтрация
```bash
ai-docs --source . --language ru --include "*.py" --exclude "tests/*"
```

### Принудительная перегенерация
```bash
ai-docs --regen modules,configs --force
```
Пересоздаст разделы модулей и конфигураций, а также перезапишет `README.md`.

---

## Конфигурация

### Через переменные окружения
```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
export AI_DOCS_THREADS=4
export AI_DOCS_LOCAL_SITE=true
```

### Через `.ai-docs.yaml`
```yaml
code_extensions:
  .py: Python
  .go: Go
  .ts: TypeScript

config_extensions:
  .yaml: YAML
  .tf: Terraform

exclude:
  - temp/*
  - *.log
  - .env
```

---

## Работа с кэшированием

Инструмент использует инкрементальную генерацию:
- При повторном запуске анализируются только изменённые файлы.
- Кэш хранится в `.ai_docs_cache/`.
- Для отключения: `--no-cache`.
- Для очистки: удалите `.ai_docs_cache/` или используйте `--regen all`.

---

## Интеграция в CI/CD

Пример для GitHub Actions:
```yaml
- name: Generate Docs
  run: |
    pip install ai-docs-gen
    ai-docs --source . --readme --mkdocs --language en
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## Поддерживаемые технологии

Инструмент автоматически распознаёт:
- **Инфраструктура**: Kubernetes, Helm, Terraform, Ansible, Docker
- **CI/CD**: GitHub Actions, GitLab CI, Jenkins
- **Мониторинг**: Prometheus, Grafana
- **Service Mesh**: Istio, Linkerd
- **Хранилища**: PostgreSQL, Redis, Kafka

Распознавание основано на анализе имён файлов, расширений и содержимого.

---

## Настройка MkDocs

При генерации `mkdocs.yml`:
- Автоматически включается плагин `mermaid2` для диаграмм.
- Навигация строится на основе `_index.json`.
- Поддерживается локальный режим (`AI_DOCS_LOCAL_SITE`), отключающий внешние ресурсы.

Сайт собирается автоматически после генерации, если указан флаг `--mkdocs`.

---

## Управление потоками

Параллельная обработка ускоряет анализ:
- По умолчанию: 4 потока.
- Настройка: `--threads 8` или `AI_DOCS_THREADS=8`.
- Ограничено семафором в асинхронных операциях.

---

## Ограничения и рекомендации

- **Макс. размер файла**: 200 КБ (настраивается через `--max-size`).
- **Игнорируемые файлы**: `.git`, `node_modules`, `.venv`, `__pycache__`, `.env`, `dist`.
- **Поддерживаемые кодировки**: UTF-8.
- **Бинарные файлы** пропускаются автоматически.

Для больших проектов рекомендуется использовать `--include` для фокусировки на ключевых директориях.

---

## Отладка и разработка

Запуск в режиме отладки:
```bash
python -m ai_docs.cli --source . --no-cache --threads 1
```

Зависимости устанавливаются вручную:
```bash
pip install -e .
```

Тесты:
```bash
pytest tests/
```

---

## Лицензия

Проект распространяется под лицензией MIT. Вклад приветствуется через PR.
