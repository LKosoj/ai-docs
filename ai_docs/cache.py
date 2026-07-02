import json
from pathlib import Path
from typing import Dict, Tuple

from .config import ConfigError, parse_int_env
from .utils import ensure_dir


class CacheError(RuntimeError):
    pass


class CacheManager:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        ensure_dir(self.cache_dir)
        self.index_path = self.cache_dir / "index.json"
        self.llm_cache_path = self.cache_dir / "llm_cache.json"

    def load_index(self) -> Dict:
        return self._read_json(self.index_path, {"files": {}, "sections": {}})

    def save_index(self, data: Dict) -> None:
        self._write_json_atomic(self.index_path, data)

    def load_llm_cache(self) -> Dict[str, str]:
        data = self._read_json(self.llm_cache_path, {})
        invalid_keys = [
            key
            for key, value in data.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if invalid_keys:
            key = invalid_keys[0]
            raise CacheError(f"Invalid LLM cache file: {self.llm_cache_path}: invalid value for key {key}")
        return data

    def save_llm_cache(self, data: Dict[str, str]) -> None:
        invalid_keys = [
            key
            for key, value in data.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if invalid_keys:
            key = invalid_keys[0]
            raise CacheError(f"Invalid LLM cache value for key {key}")
        self._write_json_atomic(self.llm_cache_path, self._prune_llm_cache(data))

    def _prune_llm_cache(self, data: Dict[str, str]) -> Dict[str, str]:
        max_entries = parse_int_env("AI_DOCS_LLM_CACHE_MAX_ENTRIES", 5000)
        if max_entries < 1:
            raise ConfigError("Invalid environment variable AI_DOCS_LLM_CACHE_MAX_ENTRIES: expected positive integer")
        if len(data) <= max_entries:
            return dict(data)
        return dict(list(data.items())[-max_entries:])

    def _read_json(self, path: Path, default: Dict) -> Dict:
        if not path.exists():
            return default
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise CacheError(f"Invalid UTF-8 cache file: {path}") from exc
        if not raw.strip():
            raise CacheError(f"Invalid JSON cache file: {path}: empty file")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CacheError(f"Invalid JSON cache file: {path}") from exc
        if not isinstance(data, dict):
            raise CacheError(f"Invalid JSON cache file: {path}: expected object")
        return data

    def _write_json_atomic(self, path: Path, data: Dict) -> None:
        ensure_dir(path.parent)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def diff_files(self, current_files: Dict[str, Dict]) -> Tuple[Dict, Dict, Dict, Dict]:
        prev = self.load_index().get("files", {})
        added = {}
        modified = {}
        deleted = {}
        unchanged = {}

        for path, meta in current_files.items():
            if path not in prev:
                added[path] = meta
                continue
            if prev[path].get("hash") != meta.get("hash"):
                modified[path] = meta
            else:
                unchanged[path] = meta

        for path, meta in prev.items():
            if path not in current_files:
                deleted[path] = meta

        return added, modified, deleted, unchanged
