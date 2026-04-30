import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from setuptools.build_meta import build_sdist


class PackagingTests(unittest.TestCase):
    def test_sdist_excludes_non_project_payload_paths(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                os.chdir(root)
                archive = Path(tmp) / build_sdist(tmp)
            finally:
                os.chdir(cwd)

            with tarfile.open(archive, "r:gz") as tar:
                names = tar.getnames()

        package_root = names[0].rstrip("/") + "/"
        payload = {
            name[len(package_root) :]
            for name in names
            if name.startswith(package_root) and name != package_root.rstrip("/")
        }

        self.assertIn("README.md", payload)
        self.assertIn("pyproject.toml", payload)
        self.assertIn("ai_docs/cli.py", payload)
        self.assertIn("ai_docs/assets/mermaid.min.js", payload)

        disallowed_prefixes = (
            ".ai-docs/",
            ".cli-proxy/",
            ".pytest_cache/",
            ".ruff_cache/",
            ".venv/",
            "ai_docs_site/",
            "build/",
            "dist/",
            "examples/",
            "logs/",
            "skills/",
            "tests/",
        )
        for path in payload:
            self.assertFalse(path.startswith(disallowed_prefixes), path)

        egg_info_paths = {
            path for path in payload if path.startswith("ai_docs_gen.egg-info/")
        }
        self.assertLessEqual(egg_info_paths, {"ai_docs_gen.egg-info/SOURCES.txt"})


if __name__ == "__main__":
    unittest.main()
