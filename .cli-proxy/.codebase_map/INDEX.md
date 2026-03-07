# Codebase Mapper Instruction Graph

Generated: 2026-03-07T07:34:06Z

This index is the entrypoint for agent instructions.

## Mandatory Workflow
1. Before any edits, read this `INDEX.md` completely.
2. Determine relevant area(s) and open matching files under `.cli-proxy/.codebase_map/nodes/*.md`.
3. Only then inspect source files and implement changes.
4. After changes, update affected node metadata (`When to update`, `Last reviewed`).
5. If node update fails, run targeted repair for that node.

## Runtime Verification and Fallback Policy (Hardcoded)
- Перед любым утверждением о runtime-поведении ОБЯЗАТЕЛЬНО проверить конкретный метод/функцию в коде и сослаться на файл:строка.
- Запрещено делать выводы по аналогии между этапами пайплайна без прямой проверки каждого этапа (decompose/dev/review/final audit).
- Если вопрос про «кто/когда вызывается», отвечать в формате пошаговой цепочки: шаг -> метод -> исполнитель -> зачем.
- При обнаружении своей неточности сначала коротко исправить факт, затем дать проверенные ссылки на код, без догадок.
- Policy matrix по fallback:
- Legacy-потоки (уже существующее поведение в проде): fallback разрешён для обратной совместимости, но должен логироваться и быть явно отражён в отчёте.
- Новый функционал и новые mode-сценарии: fallback запрещён по умолчанию; при ошибке — явный fail с причиной.
- Opt-in fallback: разрешён только после явного согласования с пользователем в текущей задаче или если он явно приходит как требование от пользователя.

## Runtime Files
- `graph.json`: topology and edges.
- `rules.yaml`: update routing rules.
- `state.json`: statuses/queues (`ok|needs_repair|degraded|invalid`).
- `api/`: optional technical interface mirror.

## Core Docs
These files are mandatory context and must be considered before major edits.
- `STACK.md`: Технологический стек, зависимости, рантаймы и инфраструктурные маркеры.
- `INTEGRATIONS.md`: Внешние/внутренние интеграции, точки входа и контракты взаимодействий.
- `ARCHITECTURE.md`: Архитектурная структура модулей, слои и их ответственность.
- `STRUCTURE.md`: Физическая структура репозитория и индексация значимых путей.
- `CONVENTIONS.md`: Кодовые конвенции, практики и стандарты реализации.
- `TESTING.md`: Подход к тестированию, расположение тестов и проверочные правила.
- `CONCERNS.md`: Риски, технический долг и зоны повышенного внимания.

## Nodes
- [ai_docs_site](nodes/ai-docs-site.md) - files: 60, source_glob: `ai_docs_site/**`
- [ai_docs](nodes/ai-docs.md) - files: 19, source_glob: `ai_docs/**`
- [tests](nodes/tests.md) - files: 4, source_glob: `tests/**`
- [documentary.skill](nodes/documentary-skill.md) - files: 1, source_glob: `documentary.skill`
- [mkdocs.yml](nodes/mkdocs-yml.md) - files: 1, source_glob: `mkdocs.yml`
- [pyproject.toml](nodes/pyproject-toml.md) - files: 1, source_glob: `pyproject.toml`
- [run_docs_bg.sh](nodes/run-docs-bg-sh.md) - files: 1, source_glob: `run_docs_bg.sh`

## Runtime Inputs
- map_dir: `/srv/git_projects/ai-docs/.cli-proxy/.codebase_map`
- changed_files: 0
