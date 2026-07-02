import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from setuptools.build_meta import build_sdist
import tomli


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

    def test_runtime_requirements_match_pyproject_dependencies(self):
        root = Path(__file__).resolve().parents[1]
        pyproject = tomli.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        project_deps = set(pyproject["project"]["dependencies"])
        requirements = {
            line.strip()
            for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

        self.assertEqual(requirements, project_deps)
        self.assertIn("watchdog", pyproject["project"]["optional-dependencies"]["watch"])

    def test_runtime_code_avoids_python39_builtin_generics(self):
        root = Path(__file__).resolve().parents[1]
        forbidden = ("tuple[", "list[", "dict[", "set[")
        offenders = []
        for path in (root / "ai_docs").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker in text:
                    offenders.append(f"{path.relative_to(root)}: {marker}")

        self.assertEqual(offenders, [])

    def test_readme_does_not_claim_config_is_auto_created(self):
        root = Path(__file__).resolve().parents[1]
        forbidden_phrases = (
            "создаётся автоматически",
            "generated automatically from current",
        )
        for name in ("README.md", "README_EN.md"):
            with self.subTest(name=name):
                text = (root / name).read_text(encoding="utf-8")
                for phrase in forbidden_phrases:
                    self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
