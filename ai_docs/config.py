import os
from pathlib import Path
from typing import Dict, Optional, Set

import yaml


class ConfigError(RuntimeError):
    pass


_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


def parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"Invalid environment variable {name}: expected boolean")


def parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid environment variable {name}: expected integer") from exc


def parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid environment variable {name}: expected float") from exc


def load_raw_config(root: Path) -> Dict[str, object]:
    config_path = root / ".ai-docs.yaml"
    if not config_path.exists():
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Invalid config file: {config_path}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Invalid config file: {config_path}: expected mapping")
    return raw


def normalize_extensions(raw: object, defaults: Dict[str, str], field: str) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    if raw is None:
        return defaults.copy()
    if isinstance(raw, dict):
        for key, value in raw.items():
            ext = str(key).strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            if value is not None and not isinstance(value, str):
                raise ConfigError(f"Invalid config field {field}: extension description must be a string")
            desc = value.strip() if isinstance(value, str) and value.strip() else defaults.get(ext, "")
            normalized[ext] = desc
        return normalized or defaults.copy()
    if isinstance(raw, list):
        for item in raw:
            ext = str(item).strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized[ext] = defaults.get(ext, "")
        return normalized or defaults.copy()
    raise ConfigError(f"Invalid config field {field}: expected mapping or list")


def normalize_excludes(raw: object) -> Set[str]:
    if raw is None:
        return set()
    if not isinstance(raw, list):
        raise ConfigError("Invalid config field exclude: expected list")
    return {str(item).strip() for item in raw if str(item).strip()}


def load_extension_config(root: Path, defaults: Dict[str, Dict[str, str]]) -> Dict[str, object]:
    raw = load_raw_config(root)
    return {
        "code_extensions": normalize_extensions(raw.get("code_extensions"), defaults["code_extensions"], "code_extensions"),
        "doc_extensions": normalize_extensions(raw.get("doc_extensions"), defaults["doc_extensions"], "doc_extensions"),
        "config_extensions": normalize_extensions(raw.get("config_extensions"), defaults["config_extensions"], "config_extensions"),
        "exclude": normalize_excludes(raw.get("exclude")),
    }


def load_prompt_overrides(root: Path) -> Dict[str, str]:
    raw = load_raw_config(root)
    section = raw.get("prompts") or {}
    if not isinstance(section, dict):
        raise ConfigError("Invalid config field prompts: expected mapping")
    result: Dict[str, str] = {}
    for key, value in section.items():
        if value is None:
            continue
        if not isinstance(value, str):
            raise ConfigError("Invalid config field prompts: values must be strings")
        if value.strip():
            result[str(key)] = value.strip()
    return result


def load_source_url(root: Path) -> Optional[str]:
    raw = load_raw_config(root)
    value = raw.get("source_url")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError("Invalid config field source_url: expected string")
    if value.strip():
        return value.strip().rstrip("/") + "/"
    return None
