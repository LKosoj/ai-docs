import json
from pathlib import Path
from typing import Dict, Tuple

from .utils import ensure_dir


class CacheManager:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        ensure_dir(self.cache_dir)
        self.index_path = self.cache_dir / "index.json"
        self.llm_cache_path = self.cache_dir / "llm_cache.json"

    def load_index(self) -> Dict:
        if not self.index_path.exists():
            return {"files": {}, "sections": {}}
        return json.loads(self.index_path.read_text(encoding="utf-8", errors="ignore"))

    def save_index(self, data: Dict) -> None:
        self.index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_llm_cache(self) -> Dict[str, str]:
        if not self.llm_cache_path.exists():
            return {}
        return json.loads(self.llm_cache_path.read_text(encoding="utf-8", errors="ignore"))

    def save_llm_cache(self, data: Dict[str, str]) -> None:
        self.llm_cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

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

