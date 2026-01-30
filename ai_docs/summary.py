from pathlib import Path
from typing import Dict, List

from .tokenizer import chunk_text
from .utils import ensure_dir


SUMMARY_PROMPT = """
Ты эксперт по технической документации. Сформируй краткое, но информативное описание файла для включения в документацию.
Укажи назначение, ключевые сущности и важные настройки. Если файл конфигурационный — перечисли ключевые параметры/секции.
Ответ строго в Markdown, без заголовка.
""".strip()


def summarize_file(content: str, file_type: str, domains: List[str], llm_client, llm_cache: Dict[str, str], model: str) -> str:
    chunks = chunk_text(content, model=model, max_tokens=1800)
    summaries = []
    for chunk in chunks:
        prompt = SUMMARY_PROMPT
        if file_type == "infra" or domains:
            prompt = SUMMARY_PROMPT + "\nФайл относится к инфраструктуре: " + ", ".join(domains)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": chunk},
        ]
        summaries.append(llm_client.chat(messages, cache=llm_cache).strip())

    if len(summaries) == 1:
        return summaries[0]

    combined = "\n\n".join(summaries)
    messages = [
        {"role": "system", "content": "Собери единое краткое резюме для документации на основе частей ниже. Ответ в Markdown."},
        {"role": "user", "content": combined},
    ]
    return llm_client.chat(messages, cache=llm_cache).strip()


def write_summary(summary_dir: Path, rel_path: str, summary: str) -> Path:
    ensure_dir(summary_dir)
    safe_name = "".join(c if c.isalnum() else "_" for c in rel_path).strip("_").lower()
    out_path = summary_dir / f"{safe_name}.md"
    out_path.write_text(summary, encoding="utf-8")
    return out_path

