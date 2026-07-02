from dataclasses import dataclass, field
from typing import Optional, Set

from .prompts import PromptStore


@dataclass
class GenerationConfig:
    prompt_store: PromptStore = field(default_factory=PromptStore)
    source_url: Optional[str] = None
    force_sections: Set[str] = field(default_factory=set)
    regen_all_threshold: int = 50


def parse_section_list(raw: Optional[str]) -> Set[str]:
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}
