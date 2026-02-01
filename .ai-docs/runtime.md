# Запуск и окружение

```markdown
# Запуск и окружение

## Подготовка окружения

Перед запуском инструмента `ai_docs` необходимо:

1. Создать файл `.env` на основе `.env.example`:
   ```bash
   cp .env.example .env
   ```

2. Указать обязательные параметры в `.env`:
   ```env
   OPENAI_API_KEY=ваш_ключ_от_openai
   OPENAI_MODEL=gpt-4o-mini
   ```

3. При использовании альтернативного LLM-провайдера (совместимого с OpenAI API), задать:
   ```env
   OPENAI_BASE_URL=https://ваш-хост/v1
   ```

4. Настроить параллельную обработку (опционально):
   ```env
   AI_DOCS_THREADS=4
   ```

## Запуск генерации документации

### Локальный репозиторий
```bash
python -m ai_docs --source ./my-project --output ./docs --mkdocs --readme --language ru
```

### Удалённый репозиторий
```bash
python -m ai_docs --source https://github.com/user/repo.git --output ./docs --mkdocs
```

### Полный пример с настройками
```bash
python -m ai_docs \
  --source ./src \
  --output ./docs \
  --mkdocs \
  --readme \
  --language ru \
  --include "*.py" "*.md" "*.yaml" \
  --exclude "*.test.py" "*.spec.js" \
  --max-size 500000 \
  --threads 6 \
  --cache-dir .ai_docs_cache \
  --local-site
```

## Ключевые аргументы CLI

| Аргумент | Назначение | По умолчанию |
|--------|-----------|-------------|
| `--source` | Путь или URL к репозиторию | — (обязательный) |
| `--output` | Директория вывода | `./output/<repo>` |
| `--mkdocs` | Генерировать `mkdocs.yml` и структуру сайта | отключено |
| `--readme` | Генерировать `README.md` | отключено |
| `--language` | Язык документации | `ru` |
| `--threads` | Количество потоков | значение `AI_DOCS_THREADS` |
| `--local-site` | Настройка MkDocs для локального просмотра | `false` |
| `--no-cache` | Отключить кэширование LLM-запросов | `false` |
| `--force` | Перезаписать существующий `README.md` | `false` |

## Работа с кэшем

- Кэш LLM-ответов хранится в `--cache-dir` (по умолчанию `.ai_docs_cache`).
- При повторном запуске неизменённые файлы не перепроцессируются.
- Для полного перезапуска:
  ```bash
  rm -rf .ai_docs_cache && python -m ai_docs --source ...
  ```

## Особенности выполнения

- При указании URL репозиторий клонируется временно (`--depth 1`) и удаляется после завершения.
- Бинарные файлы и символические ссылки автоматически пропускаются.
- Файлы размером более `--max-size` (байт) игнорируются.
- Правила `.gitignore` и `.build_ignore` применяются автоматически.
- Для локального просмотра с `--local-site` в `mkdocs.yml` отключаются `site_url` и `use_directory_urls`.

## Требования

- Python 3.9+
- Библиотеки: `openai`, `tiktoken`, `pathspec`, `python-dotenv`, `pyyaml`
- Доступ к LLM через API (OpenAI или совместимый провайдер)
```
