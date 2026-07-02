import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict

from .generator_shared import first_paragraph
from .prompts import CONFIG_TAG, MODULE_TAG, OVERVIEW_TAG, PromptStore, active as _prompts
from .tokenizer import chunk_text
from .utils import ensure_dir, sha256_text


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


def _prompt_store(prompt_store: Optional[PromptStore]) -> PromptStore:
    return prompt_store or _prompts()


async def _normalize_module_summary(
    summary: str,
    llm_client,
    llm_cache: Dict[str, str],
    prompt_store: Optional[PromptStore] = None,
) -> str:
    if not _needs_doxygen_fix(summary):
        return summary
    messages = [
        {"role": "system", "content": _prompt_store(prompt_store).module_summary_reformat()},
        {"role": "user", "content": summary},
    ]
    return (await llm_client.chat(messages, cache=llm_cache)).strip()


async def _normalize_config_summary(
    summary: str,
    llm_client,
    llm_cache: Dict[str, str],
    prompt_store: Optional[PromptStore] = None,
) -> str:
    if not _needs_doxygen_fix(summary):
        return _format_config_blocks(summary)
    messages = [
        {"role": "system", "content": _prompt_store(prompt_store).config_summary_reformat()},
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
) -> Tuple[str, str]:
    response = await _summarize_chunks(content, prompt, combine_prompt, llm_client, llm_cache, model)
    overview_summary = _extract_tagged_block(response, OVERVIEW_TAG)
    detailed_summary = _extract_tagged_block(response, detail_tag)
    return overview_summary, detailed_summary


def _summary_prompt(file_type: str, domains: List[str], prompt_store: Optional[PromptStore]) -> str:
    base = _prompt_store(prompt_store).summary()
    if file_type == "infra" or domains:
        return base + "\nФайл относится к инфраструктуре: " + ", ".join(domains)
    return base


async def summarize_file_outputs(
    content: str,
    file_type: str,
    domains: List[str],
    llm_client,
    llm_cache: Dict[str, str],
    model: str,
    include_module_summary: bool = False,
    include_config_summary: bool = False,
    prompt_store: Optional[PromptStore] = None,
) -> SummaryOutputs:
    outputs: SummaryOutputs = {}

    if include_config_summary and file_type == "config":
        overview_summary, config_summary = await _summarize_structured_chunks(
            content,
            _prompt_store(prompt_store).config_summary_bundle(),
            _prompt_store(prompt_store).config_summary_bundle_combine(),
            CONFIG_TAG,
            llm_client,
            llm_cache,
            model,
        )
        config_summary = await _normalize_config_summary(
            config_summary,
            llm_client,
            llm_cache,
            prompt_store,
        )
        outputs["config_summary"] = config_summary
        outputs["summary"] = overview_summary or first_paragraph(config_summary) or config_summary
        return outputs

    if include_module_summary:
        overview_summary, module_summary = await _summarize_structured_chunks(
            content,
            _prompt_store(prompt_store).module_summary_bundle(),
            _prompt_store(prompt_store).module_summary_bundle_combine(),
            MODULE_TAG,
            llm_client,
            llm_cache,
            model,
        )
        module_summary = await _normalize_module_summary(
            module_summary,
            llm_client,
            llm_cache,
            prompt_store,
        )
        outputs["module_summary"] = module_summary
        outputs["summary"] = overview_summary or first_paragraph(module_summary) or module_summary
        return outputs

    outputs["summary"] = await _summarize_chunks(
        content,
        _summary_prompt(file_type, domains, prompt_store),
        _prompt_store(prompt_store).summary_combine(),
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
    prompt_store: Optional[PromptStore] = None,
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
        prompt_store=prompt_store,
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
