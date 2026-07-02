"""Load optional site-level settings from .ai-docs.yaml.

Currently only `source_url` is used: a base URL that citations prepend to
relative file paths so generated docs can link back to source in Git/Gitlab.

The process-wide singleton is kept for older direct callers. The main generator
pipeline passes `source_url` explicitly via `GenerationConfig`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import load_source_url as _load_source_url


_source_url: Optional[str] = None


def configure_source_url(url: Optional[str]) -> None:
    global _source_url
    _source_url = url


def active_source_url() -> Optional[str]:
    return _source_url


def load_source_url(root: Path) -> Optional[str]:
    return _load_source_url(root)


def format_citation(rel_path: str, source_url: Optional[str]) -> str:
    path_repr = rel_path.replace("\\", "/")
    if source_url:
        return f"*Источник:* [`{path_repr}`]({source_url}{path_repr})"
    return f"*Источник:* `{path_repr}`"
