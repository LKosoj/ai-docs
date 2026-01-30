from typing import Dict, List


def format_changes_md(added: Dict, modified: Dict, deleted: Dict, regenerated_sections: List[str], summary: str) -> str:
    def _fmt_list(title: str, items: Dict) -> str:
        if not items:
            return f"## {title}\n\n- нет\n"
        lines = "\n".join([f"- {path}" for path in sorted(items.keys())])
        return f"## {title}\n\n{lines}\n"

    md = "# Изменения с последней генерации\n\n"
    md += _fmt_list("Добавленные файлы", added)
    md += _fmt_list("Изменённые файлы", modified)
    md += _fmt_list("Удалённые файлы", deleted)

    md += "## Перегенерированные разделы\n\n"
    if regenerated_sections:
        md += "\n".join([f"- {name}" for name in regenerated_sections]) + "\n"
    else:
        md += "- нет\n"

    md += "\n## Краткое резюме\n\n"
    md += summary.strip() + "\n"
    return md

