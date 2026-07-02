import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_docs.cache import CacheError, CacheManager
from ai_docs.generator_cache import build_masked_snapshot


class CacheManagerTests(unittest.TestCase):
    def test_diff_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheManager(Path(tmp))
            current = {
                "a.txt": {"hash": "1"},
                "b.txt": {"hash": "2"},
            }
            added, modified, deleted, unchanged = cache.diff_files(current)
            self.assertIn("a.txt", added)
            self.assertIn("b.txt", added)
            self.assertEqual(modified, {})
            self.assertEqual(deleted, {})

            cache.save_index({"files": current, "sections": {}})
            current2 = {
                "a.txt": {"hash": "1"},
                "b.txt": {"hash": "3"},
                "c.txt": {"hash": "4"},
            }
            added, modified, deleted, unchanged = cache.diff_files(current2)
            self.assertIn("c.txt", added)
            self.assertIn("b.txt", modified)
            self.assertIn("a.txt", unchanged)
            self.assertEqual(deleted, {})

            cache.save_index({"files": current2, "sections": {}})
            current3 = {
                "a.txt": {"hash": "1"},
            }
            added, modified, deleted, unchanged = cache.diff_files(current3)
            self.assertIn("b.txt", deleted)
            self.assertIn("c.txt", deleted)

    def test_build_masked_snapshot_preserves_unmasked_previous_files(self):
        prev = {
            "a.py": {"hash": "old-a", "summary_path": "a.md"},
            "b.py": {"hash": "old-b", "summary_path": "b.md"},
            "deleted.py": {"hash": "old-d", "summary_path": "d.md"},
        }
        current = {
            "a.py": {"hash": "new-a", "summary_path": "new-a.md"},
            "b.py": {"hash": "new-b"},
        }

        snapshot = build_masked_snapshot(
            current,
            prev,
            changed_paths={"a.py"},
            deleted_paths={"deleted.py"},
        )

        self.assertEqual(snapshot["a.py"]["hash"], "new-a")
        self.assertEqual(snapshot["b.py"]["hash"], "old-b")
        self.assertNotIn("deleted.py", snapshot)

    def test_corrupt_index_raises_cache_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheManager(Path(tmp))
            cache.index_path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(CacheError):
                cache.load_index()

    def test_corrupt_llm_cache_raises_cache_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheManager(Path(tmp))
            cache.llm_cache_path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(CacheError):
                cache.load_llm_cache()

    def test_invalid_llm_cache_values_raise_cache_error(self):
        cases = [
            {"key": None},
            {"key": ""},
            {"key": "   "},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as tmp:
                    cache = CacheManager(Path(tmp))
                    cache.llm_cache_path.write_text(json.dumps(payload), encoding="utf-8")

                    with self.assertRaises(CacheError):
                        cache.load_llm_cache()

    def test_invalid_utf8_cache_raises_cache_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheManager(Path(tmp))
            cache.index_path.write_bytes(b'{"files": {}, "sections": {}}\xff')

            with self.assertRaises(CacheError):
                cache.load_index()

    def test_empty_existing_cache_raises_cache_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheManager(Path(tmp))
            cache.index_path.write_text("", encoding="utf-8")

            with self.assertRaises(CacheError):
                cache.load_index()

    def test_save_index_uses_atomic_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheManager(Path(tmp))

            cache.save_index({"files": {"a.py": {"hash": "1"}}, "sections": {}})

            self.assertTrue(cache.index_path.exists())
            self.assertFalse((Path(tmp) / ".index.json.tmp").exists())
            self.assertEqual(cache.load_index()["files"]["a.py"]["hash"], "1")

    def test_save_llm_cache_prunes_to_configured_max_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheManager(Path(tmp))
            env = {**os.environ, "AI_DOCS_LLM_CACHE_MAX_ENTRIES": "2"}

            with patch.dict(os.environ, env, clear=True):
                cache.save_llm_cache({"a": "one", "b": "two", "c": "three"})

            self.assertEqual(cache.load_llm_cache(), {"b": "two", "c": "three"})


if __name__ == "__main__":
    unittest.main()
