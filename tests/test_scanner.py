import tempfile
import unittest
from pathlib import Path

from ai_docs.scanner import scan_source


class ScannerTests(unittest.TestCase):
    def test_scan_local_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print('hi')", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM python:3.11", encoding="utf-8")
            (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
            (root / "ignored.txt").write_text("secret", encoding="utf-8")
            venv_dir = root / ".venv" / "lib" / "python3.10" / "site-packages"
            venv_dir.mkdir(parents=True)
            (venv_dir / "inside.py").write_text("print('no')", encoding="utf-8")

            result = scan_source(str(root))
            paths = {f["path"] for f in result.files}
            self.assertIn("app.py", paths)
            self.assertIn("Dockerfile", paths)
            self.assertNotIn("ignored.txt", paths)
            self.assertNotIn(".venv/lib/python3.10/site-packages/inside.py", paths)


if __name__ == "__main__":
    unittest.main()
