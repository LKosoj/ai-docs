import asyncio
from pathlib import Path
from typing import Dict, List, TypedDict

from .generator_shared import first_paragraph
from .tokenizer import chunk_text
from .utils import ensure_dir, sha256_text


SUMMARY_PROMPT = """
Ты эксперт по технической документации. Сформируй краткое, но информативное описание файла для включения в документацию.
Укажи назначение, ключевые сущности и важные настройки. Если файл конфигурационный — перечисли ключевые параметры/секции.
Ответ строго в Markdown, без заголовка. Не используй блоки кода и не оборачивай текст в ```markdown.
""".strip()

SUMMARY_COMBINE_PROMPT = """
Собери единое краткое резюме для документации на основе частей ниже.
Сохрани только важные сущности, назначение файла и существенные настройки.
Ответ в Markdown, без заголовка и без блоков кода.
""".strip()

OVERVIEW_TAG = "overview_summary"
MODULE_TAG = "module_summary"
CONFIG_TAG = "config_summary"

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

MODULE_SUMMARY_BUNDLE_PROMPT = f"""
Ты технический писатель. Верни ответ строго в формате:
<{OVERVIEW_TAG}>
Краткое резюме модуля для overview-разделов, 2–4 предложения.
</{OVERVIEW_TAG}>
<{MODULE_TAG}>
{MODULE_SUMMARY_PROMPT}
</{MODULE_TAG}>

Не добавляй никакого текста вне этих тегов.
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

MODULE_SUMMARY_BUNDLE_COMBINE_PROMPT = f"""
На основе частей ниже собери итоговый ответ строго в формате:
<{OVERVIEW_TAG}>
Краткое резюме модуля для overview-разделов, 2–4 предложения.
</{OVERVIEW_TAG}>
<{MODULE_TAG}>
Итоговая документация модуля в строгом Doxygen‑стиле.
</{MODULE_TAG}>

Не добавляй никакого текста вне этих тегов.
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

CONFIG_SUMMARY_BUNDLE_PROMPT = f"""
Ты технический писатель. Верни ответ строго в формате:
<{OVERVIEW_TAG}>
Краткое резюме конфигурационного файла для overview-разделов, 2–4 предложения.
</{OVERVIEW_TAG}>
<{CONFIG_TAG}>
{CONFIG_SUMMARY_PROMPT}
</{CONFIG_TAG}>

Не добавляй никакого текста вне этих тегов.
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

CONFIG_SUMMARY_BUNDLE_COMBINE_PROMPT = f"""
На основе частей ниже собери итоговый ответ строго в формате:
<{OVERVIEW_TAG}>
Краткое резюме конфигурационного файла для overview-разделов, 2–4 предложения.
</{OVERVIEW_TAG}>
<{CONFIG_TAG}>
Итоговое описание конфигурационного файла в универсальном стиле.
</{CONFIG_TAG}>

Не добавляй никакого текста вне этих тегов.
""".strip()


class SummaryOutputs(TypedDict, total=False):
    summary: str
    module_summary: str
    config_summary: str


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


async def _normalize_module_summary(summary: str, llm_client, llm_cache: Dict[str, str]) -> str:
    if not _needs_doxygen_fix(summary):
        return summary
    messages = [
        {"role": "system", "content": MODULE_SUMMARY_REFORMAT_PROMPT},
        {"role": "user", "content": summary},
    ]
    return (await llm_client.chat(messages, cache=llm_cache)).strip()


async def _normalize_config_summary(summary: str, llm_client, llm_cache: Dict[str, str]) -> str:
    if not _needs_doxygen_fix(summary):
        return _format_config_blocks(summary)
    messages = [
        {"role": "system", "content": CONFIG_SUMMARY_REFORMAT_PROMPT},
        {"role": "user", "content": summary},
    ]
    return _format_config_blocks((await llm_client.chat(messages, cache=llm_cache)).strip())


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


def _extract_tagged_block(text: str, tag: str) -> str:
    start = f"<{tag}>"
    end = f"</{tag}>"
    start_idx = text.find(start)
    end_idx = text.find(end)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        return ""
    start_idx += len(start)
    return text[start_idx:end_idx].strip()


async def _request_summary(
    prompt: str,
    content: str,
    llm_client,
    llm_cache: Dict[str, str],
) -> str:
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content},
    ]
    return _strip_fenced_markdown((await llm_client.chat(messages, cache=llm_cache)).strip())


async def _summarize_chunks(
    content: str,
    prompt: str,
    combine_prompt: str,
    llm_client,
    llm_cache: Dict[str, str],
    model: str,
) -> str:
    chunks = chunk_text(content, model=model, max_tokens=1800)
    if not chunks:
        return ""

    partials = await asyncio.gather(
        *(_request_summary(prompt, chunk, llm_client, llm_cache) for chunk in chunks)
    )
    partials = [item for item in partials if item]
    if not partials:
        return ""
    if len(partials) == 1:
        return partials[0]
    combined = "\n\n".join(partials)
    return await _request_summary(combine_prompt, combined, llm_client, llm_cache)


async def _summarize_structured_chunks(
    content: str,
    prompt: str,
    combine_prompt: str,
    detail_tag: str,
    llm_client,
    llm_cache: Dict[str, str],
    model: str,
) -> tuple[str, str]:
    response = await _summarize_chunks(content, prompt, combine_prompt, llm_client, llm_cache, model)
    overview_summary = _extract_tagged_block(response, OVERVIEW_TAG)
    detailed_summary = _extract_tagged_block(response, detail_tag)
    return overview_summary, detailed_summary


def _summary_prompt(file_type: str, domains: List[str]) -> str:
    if file_type == "infra" or domains:
        return SUMMARY_PROMPT + "\nФайл относится к инфраструктуре: " + ", ".join(domains)
    return SUMMARY_PROMPT


async def summarize_file_outputs(
    content: str,
    file_type: str,
    domains: List[str],
    llm_client,
    llm_cache: Dict[str, str],
    model: str,
    include_module_summary: bool = False,
    include_config_summary: bool = False,
) -> SummaryOutputs:
    outputs: SummaryOutputs = {}

    if include_config_summary and file_type == "config":
        overview_summary, config_summary = await _summarize_structured_chunks(
            content,
            CONFIG_SUMMARY_BUNDLE_PROMPT,
            CONFIG_SUMMARY_BUNDLE_COMBINE_PROMPT,
            CONFIG_TAG,
            llm_client,
            llm_cache,
            model,
        )
        config_summary = await _normalize_config_summary(config_summary, llm_client, llm_cache)
        outputs["config_summary"] = config_summary
        outputs["summary"] = overview_summary or first_paragraph(config_summary) or config_summary
        return outputs

    if include_module_summary:
        overview_summary, module_summary = await _summarize_structured_chunks(
            content,
            MODULE_SUMMARY_BUNDLE_PROMPT,
            MODULE_SUMMARY_BUNDLE_COMBINE_PROMPT,
            MODULE_TAG,
            llm_client,
            llm_cache,
            model,
        )
        module_summary = await _normalize_module_summary(module_summary, llm_client, llm_cache)
        outputs["module_summary"] = module_summary
        outputs["summary"] = overview_summary or first_paragraph(module_summary) or module_summary
        return outputs

    outputs["summary"] = await _summarize_chunks(
        content,
        _summary_prompt(file_type, domains),
        SUMMARY_COMBINE_PROMPT,
        llm_client,
        llm_cache,
        model,
    )
    return outputs


async def summarize_file(
    content: str,
    file_type: str,
    domains: List[str],
    llm_client,
    llm_cache: Dict[str, str],
    model: str,
    detailed: bool = False,
) -> str:
    outputs = await summarize_file_outputs(
        content,
        file_type,
        domains,
        llm_client,
        llm_cache,
        model,
        include_module_summary=detailed and file_type != "config",
        include_config_summary=detailed and file_type == "config",
    )
    if detailed and file_type == "config":
        return outputs.get("config_summary", "")
    if detailed:
        return outputs.get("module_summary", "")
    return outputs.get("summary", "")


def write_summary(summary_dir: Path, rel_path: str, summary: str) -> Path:
    ensure_dir(summary_dir)
    safe_name = "".join(c if c.isalnum() else "_" for c in rel_path).strip("_")
    suffix = sha256_text(rel_path)[:12]
    out_path = summary_dir / f"{safe_name}_{suffix}.md"
    out_path.write_text(summary, encoding="utf-8")
    return out_path
