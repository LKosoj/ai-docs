"""Load optional site-level settings from .ai-docs.yaml.

Currently only `source_url` is used — a base URL that citations prepend to
relative file paths so generated docs can link back to source in Git/Gitlab.

The module exposes a process-wide singleton so deeply-nested callers (e.g.
generator_sections) can read the URL without every caller threading it through
the signature chain. Configure once in the CLI entrypoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


_source_url: Optional[str] = None


def configure_source_url(url: Optional[str]) -> None:
    global _source_url
    _source_url = url


def active_source_url() -> Optional[str]:
    return _source_url


def load_source_url(root: Path) -> Optional[str]:
    config_path = root / ".ai-docs.yaml"
    if not config_path.exists():
        return None
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8", errors="ignore")) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(raw, dict):
        return None
    value = raw.get("source_url")
    if isinstance(value, str) and value.strip():
        return value.strip().rstrip("/") + "/"
    return None


def format_citation(rel_path: str, source_url: Optional[str]) -> str:
    path_repr = rel_path.replace("\\", "/")
    if source_url:
        return f"*Источник:* [`{path_repr}`]({source_url}{path_repr})"
    return f"*Источник:* `{path_repr}`"
