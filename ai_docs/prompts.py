"""Centralized prompt templates with optional user overrides from .ai-docs.yaml.

Each prompt is identified by a stable key. Users can override any subset of
prompts by adding a `prompts:` section to `.ai-docs.yaml`:

    prompts:
      summary: |
        Your custom summary prompt here.
      module_summary: |
        Your custom module summary prompt here.

Unknown keys are ignored. Missing keys fall back to built-in defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import yaml


OVERVIEW_TAG = "overview_summary"
MODULE_TAG = "module_summary"
CONFIG_TAG = "config_summary"


_DEFAULTS: Dict[str, str] = {
    "summary": (
        "Ты эксперт по технической документации. Сформируй краткое, но информативное "
        "описание файла для включения в документацию.\n"
        "Укажи назначение, ключевые сущности и важные настройки. "
        "Если файл конфигурационный — перечисли ключевые параметры/секции.\n"
        "Ответ строго в Markdown, без заголовка. "
        "Не используй блоки кода и не оборачивай текст в ```markdown."
    ),
    "summary_combine": (
        "Собери единое краткое резюме для документации на основе частей ниже.\n"
        "Сохрани только важные сущности, назначение файла и существенные настройки.\n"
        "Ответ в Markdown, без заголовка и без блоков кода."
    ),
    "module_summary": (
        "Ты технический писатель. Сформируй документацию модуля в стиле Doxygen.\n"
        "Сначала дай краткое верхнеуровневое описание модуля (2–4 предложения).\n"
        "Затем, если есть важные структуры данных/типы, добавь блок:\n"
        "Ключевые структуры данных\n"
        "<имя> — <краткое описание>\n\n"
        "Далее перечисли функции/процедуры и классы строго в Doxygen‑формате.\n"
        "Для функций/процедур используй формат:\n\n"
        "<сигнатура>\n"
        "<краткое назначение одной строкой>\n"
        "Аргументы\n"
        "<имя> — <описание>\n"
        "Возвращает\n"
        "<описание>\n"
        "Исключения\n"
        "<описание>\n\n"
        "Для классов используй формат:\n"
        "class <имя>\n"
        "<краткое назначение одной строкой>\n"
        "Поля\n"
        "<имя> — <описание>\n"
        "Методы\n"
        "<сигнатура> — <краткое назначение>\n\n"
        "Если аргументов/возвращаемого значения/исключений/полей нет — "
        "соответствующий блок пропускай.\n"
        "Разделяй сущности строкой из трёх дефисов: `---`.\n"
        "Не используй заголовки Markdown, списки, подзаголовки вроде \"Основные функции\".\n"
        "Ответ строго в Markdown, без заголовка документа, сохраняя последовательность блоков."
    ),
    "module_summary_reformat": (
        "Переформатируй текст в строгий Doxygen‑стиль для модуля.\n"
        "Требования:\n"
        "- Без заголовков Markdown, без списков, без блоков кода.\n"
        "- Структура: краткое описание модуля; затем (если есть) \"Ключевые структуры данных\" "
        "с линиями \"<имя> — <описание>\".\n"
        "- Далее только сущности (функции/процедуры/классы) в формате:\n"
        "<сигнатура>\n"
        "<краткое назначение одной строкой>\n"
        "Аргументы\n"
        "<имя> — <описание>\n"
        "Возвращает\n"
        "<описание>\n"
        "Исключения\n"
        "<описание>\n"
        "Для классов:\n"
        "class <имя>\n"
        "<краткое назначение одной строкой>\n"
        "Поля\n"
        "<имя> — <описание>\n"
        "Методы\n"
        "<сигнатура> — <краткое назначение>\n\n"
        "Если блок пустой — не выводи его. Между сущностями ставь строку `---`.\n"
        "Ответ строго в Markdown без заголовка документа."
    ),
    "config_summary": (
        "Ты технический писатель. Сформируй описание конфигурационного файла в универсальном стиле.\n"
        "Сначала дай краткое описание файла (2–4 предложения).\n"
        "Затем блок:\n"
        "Секции и ключи\n"
        "<секция/ключ> — <описание>\n\n"
        "Далее (если есть важные параметры) добавь блок:\n"
        "Важные параметры\n"
        "<параметр> — <описание>\n\n"
        "Не используй заголовки Markdown, списки, нумерацию и блоки кода.\n"
        "Ответ строго в Markdown без заголовка документа, соблюдай указанные блоки."
    ),
    "config_summary_reformat": (
        "Переформатируй текст в универсальный конфиг-стиль.\n"
        "Требования:\n"
        "- Без заголовков Markdown, списков, нумерации и блоков кода.\n"
        "- Структура: краткое описание файла; затем блок \"Секции и ключи\" с линиями "
        "\"<секция/ключ> — <описание>\".\n"
        "- Далее (если есть) блок \"Важные параметры\" с линиями \"<параметр> — <описание>\".\n"
        "Если блок пустой — не выводи его.\n"
        "Ответ строго в Markdown без заголовка документа."
    ),
}


def _bundle_module_prompt(module_prompt: str) -> str:
    return (
        "Ты технический писатель. Верни ответ строго в формате:\n"
        f"<{OVERVIEW_TAG}>\n"
        "Краткое резюме модуля для overview-разделов, 2–4 предложения.\n"
        f"</{OVERVIEW_TAG}>\n"
        f"<{MODULE_TAG}>\n"
        f"{module_prompt}\n"
        f"</{MODULE_TAG}>\n\n"
        "Не добавляй никакого текста вне этих тегов."
    )


def _bundle_module_combine() -> str:
    return (
        "На основе частей ниже собери итоговый ответ строго в формате:\n"
        f"<{OVERVIEW_TAG}>\n"
        "Краткое резюме модуля для overview-разделов, 2–4 предложения.\n"
        f"</{OVERVIEW_TAG}>\n"
        f"<{MODULE_TAG}>\n"
        "Итоговая документация модуля в строгом Doxygen‑стиле.\n"
        f"</{MODULE_TAG}>\n\n"
        "Не добавляй никакого текста вне этих тегов."
    )


def _bundle_config_prompt(config_prompt: str) -> str:
    return (
        "Ты технический писатель. Верни ответ строго в формате:\n"
        f"<{OVERVIEW_TAG}>\n"
        "Краткое резюме конфигурационного файла для overview-разделов, 2–4 предложения.\n"
        f"</{OVERVIEW_TAG}>\n"
        f"<{CONFIG_TAG}>\n"
        f"{config_prompt}\n"
        f"</{CONFIG_TAG}>\n\n"
        "Не добавляй никакого текста вне этих тегов."
    )


def _bundle_config_combine() -> str:
    return (
        "На основе частей ниже собери итоговый ответ строго в формате:\n"
        f"<{OVERVIEW_TAG}>\n"
        "Краткое резюме конфигурационного файла для overview-разделов, 2–4 предложения.\n"
        f"</{OVERVIEW_TAG}>\n"
        f"<{CONFIG_TAG}>\n"
        "Итоговое описание конфигурационного файла в универсальном стиле.\n"
        f"</{CONFIG_TAG}>\n\n"
        "Не добавляй никакого текста вне этих тегов."
    )


class PromptStore:
    def __init__(self, overrides: Optional[Dict[str, str]] = None):
        self._overrides = overrides or {}

    def get(self, key: str) -> str:
        if key in self._overrides:
            return self._overrides[key]
        if key not in _DEFAULTS:
            raise KeyError(f"Unknown prompt key: {key!r}")
        return _DEFAULTS[key]

    # Convenience accessors used by summary.py (bundled/reformat variants are
    # computed from the base prompts so user overrides propagate consistently).
    def summary(self) -> str:
        return self.get("summary")

    def summary_combine(self) -> str:
        return self.get("summary_combine")

    def module_summary_bundle(self) -> str:
        return _bundle_module_prompt(self.get("module_summary"))

    def module_summary_bundle_combine(self) -> str:
        return _bundle_module_combine()

    def module_summary_reformat(self) -> str:
        return self.get("module_summary_reformat")

    def config_summary_bundle(self) -> str:
        return _bundle_config_prompt(self.get("config_summary"))

    def config_summary_bundle_combine(self) -> str:
        return _bundle_config_combine()

    def config_summary_reformat(self) -> str:
        return self.get("config_summary_reformat")


def load_prompt_overrides(root: Path) -> Dict[str, str]:
    """Read the `prompts:` section from .ai-docs.yaml, if present."""
    config_path = root / ".ai-docs.yaml"
    if not config_path.exists():
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8", errors="ignore")) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(raw, dict):
        return {}
    section = raw.get("prompts") or {}
    if not isinstance(section, dict):
        return {}
    result: Dict[str, str] = {}
    for key, value in section.items():
        if isinstance(value, str) and value.strip():
            result[str(key)] = value.strip()
    return result


_active_store: PromptStore = PromptStore()


def configure(overrides: Optional[Dict[str, str]] = None) -> None:
    """Install the active prompt store for the current process."""
    global _active_store
    _active_store = PromptStore(overrides or {})


def active() -> PromptStore:
    return _active_store


__all__ = [
    "PromptStore",
    "configure",
    "active",
    "load_prompt_overrides",
    "OVERVIEW_TAG",
    "MODULE_TAG",
    "CONFIG_TAG",
]
