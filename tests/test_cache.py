import json
import tempfile
from pathlib import Path
import unittest

from ai_docs.cache import CacheManager


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


if __name__ == "__main__":
    unittest.main()
