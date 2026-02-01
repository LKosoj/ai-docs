from pathlib import Path
from typing import Dict, List

from .tokenizer import chunk_text
from .utils import ensure_dir


SUMMARY_PROMPT = """
Ты эксперт по технической документации. Сформируй краткое, но информативное описание файла для включения в документацию.
Укажи назначение, ключевые сущности и важные настройки. Если файл конфигурационный — перечисли ключевые параметры/секции.
Ответ строго в Markdown, без заголовка. Не используй блоки кода и не оборачивай текст в ```markdown.
""".strip()

MODULE_SUMMARY_PROMPT = """
Ты технический писатель. Сформируй документацию модуля в стиле Doxygen.
Сначала дай краткое верхнеуровневое описание модуля (2–4 предложения).
Затем, если есть важные структуры данных/типы, добавь блок:
Ключевые структуры данных
<имя> — <краткое описание>

Далее перечисли функции/процедуры и классы строго в Doxygen‑формате.
Для функций/процедур используй формат:

<сигнатура>
<краткое назначение одной строкой>
Аргументы
<имя> — <описание>
Возвращает
<описание>
Исключения
<описание>

Для классов используй формат:
class <имя>
<краткое назначение одной строкой>
Поля
<имя> — <описание>
Методы
<сигнатура> — <краткое назначение>

Если аргументов/возвращаемого значения/исключений/полей нет — соответствующий блок пропускай.
Разделяй сущности строкой из трёх дефисов: `---`.
Не используй заголовки Markdown, списки, подзаголовки вроде "Основные функции".
Ответ строго в Markdown, без заголовка документа, сохраняя последовательность блоков.
""".strip()

MODULE_SUMMARY_REFORMAT_PROMPT = """
Переформатируй текст в строгий Doxygen‑стиль для модуля.
Требования:
- Без заголовков Markdown, без списков, без блоков кода.
- Структура: краткое описание модуля; затем (если есть) "Ключевые структуры данных" с линиями "<имя> — <описание>".
- Далее только сущности (функции/процедуры/классы) в формате:
<сигнатура>
<краткое назначение одной строкой>
Аргументы
<имя> — <описание>
Возвращает
<описание>
Исключения
<описание>
Для классов:
class <имя>
<краткое назначение одной строкой>
Поля
<имя> — <описание>
Методы
<сигнатура> — <краткое назначение>

Если блок пустой — не выводи его. Между сущностями ставь строку `---`.
Ответ строго в Markdown без заголовка документа.
""".strip()

CONFIG_SUMMARY_PROMPT = """
Ты технический писатель. Сформируй описание конфигурационного файла в универсальном стиле.
Сначала дай краткое описание файла (2–4 предложения).
Затем блок:
Секции и ключи
<секция/ключ> — <описание>

Далее (если есть важные параметры) добавь блок:
Важные параметры
<параметр> — <описание>

Не используй заголовки Markdown, списки, нумерацию и блоки кода.
Ответ строго в Markdown без заголовка документа, соблюдай указанные блоки.
""".strip()

CONFIG_SUMMARY_REFORMAT_PROMPT = """
Переформатируй текст в универсальный конфиг-стиль.
Требования:
- Без заголовков Markdown, списков, нумерации и блоков кода.
- Структура: краткое описание файла; затем блок "Секции и ключи" с линиями "<секция/ключ> — <описание>".
- Далее (если есть) блок "Важные параметры" с линиями "<параметр> — <описание>".
Если блок пустой — не выводи его.
Ответ строго в Markdown без заголовка документа.
""".strip()


def _needs_doxygen_fix(text: str) -> bool:
    if "```" in text:
        return True
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return True
        if stripped.startswith(("-", "*", "•")):
            return True
        if stripped[:2].isdigit() and stripped[1] == ".":
            return True
    lowered = text.lower()
    noisy_markers = [
        "основные функции",
        "основные возможности",
        "обработка ошибок",
        "интеграции",
        "ключевые структуры данных:",
        "##",
    ]
    return any(marker in lowered for marker in noisy_markers)


def _normalize_module_summary(
    summary: str, llm_client, llm_cache: Dict[str, str]
) -> str:
    if not _needs_doxygen_fix(summary):
        return summary
    messages = [
        {"role": "system", "content": MODULE_SUMMARY_REFORMAT_PROMPT},
        {"role": "user", "content": summary},
    ]
    return llm_client.chat(messages, cache=llm_cache).strip()


def _normalize_config_summary(summary: str, llm_client, llm_cache: Dict[str, str]) -> str:
    if not _needs_doxygen_fix(summary):
        return _format_config_blocks(summary)
    messages = [
        {"role": "system", "content": CONFIG_SUMMARY_REFORMAT_PROMPT},
        {"role": "user", "content": summary},
    ]
    return _format_config_blocks(llm_client.chat(messages, cache=llm_cache).strip())


def _format_config_blocks(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return text.strip()
    output: List[str] = []
    i = 0
    headers = {"Секции и ключи", "Важные параметры"}
    while i < len(lines):
        line = lines[i].strip()
        if line in headers:
            entries: List[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() not in headers:
                entries.append(lines[i].strip())
                i += 1
            output.append(line)
            if entries:
                output.append("<br>\n".join(entries))
            continue
        output.append(line)
        i += 1
    return "\n\n".join(output).strip()


def _strip_fenced_markdown(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return text


def summarize_file(
    content: str,
    file_type: str,
    domains: List[str],
    llm_client,
    llm_cache: Dict[str, str],
    model: str,
    detailed: bool = False,
) -> str:
    chunks = chunk_text(content, model=model, max_tokens=1800)
    summaries = []
    for chunk in chunks:
        if detailed and file_type == "config":
            prompt = CONFIG_SUMMARY_PROMPT
        else:
            prompt = MODULE_SUMMARY_PROMPT if detailed else SUMMARY_PROMPT
        if not detailed and (file_type == "infra" or domains):
            prompt = SUMMARY_PROMPT + "\nФайл относится к инфраструктуре: " + ", ".join(domains)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": chunk},
        ]
        summaries.append(_strip_fenced_markdown(llm_client.chat(messages, cache=llm_cache).strip()))

    if len(summaries) == 1:
        result = summaries[0]
        if detailed and file_type == "config":
            return _normalize_config_summary(result, llm_client, llm_cache)
        if detailed:
            return _normalize_module_summary(result, llm_client, llm_cache)
        return result

    combined = "\n\n".join(summaries)
    if detailed and file_type == "config":
        messages = [
            {"role": "system", "content": CONFIG_SUMMARY_REFORMAT_PROMPT},
            {"role": "user", "content": combined},
        ]
    elif detailed:
        messages = [
            {"role": "system", "content": MODULE_SUMMARY_REFORMAT_PROMPT},
            {"role": "user", "content": combined},
        ]
    else:
        messages = [
            {"role": "system", "content": "Собери единое краткое резюме для документации на основе частей ниже. Ответ в Markdown."},
            {"role": "user", "content": combined},
        ]
    result = _strip_fenced_markdown(llm_client.chat(messages, cache=llm_cache).strip())
    if detailed and file_type == "config":
        return _normalize_config_summary(result, llm_client, llm_cache)
    if detailed:
        return _normalize_module_summary(result, llm_client, llm_cache)
    return result


def write_summary(summary_dir: Path, rel_path: str, summary: str) -> Path:
    ensure_dir(summary_dir)
    safe_name = "".join(c if c.isalnum() else "_" for c in rel_path).strip("_").lower()
    out_path = summary_dir / f"{safe_name}.md"
    out_path.write_text(summary, encoding="utf-8")
    return out_path
