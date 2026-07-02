import unittest

from ai_docs.generator_shared import collect_dependencies, collect_test_info


class GeneratorSharedTests(unittest.TestCase):
    def test_collect_dependencies_reads_pep621_and_requirements(self):
        files = {
            "pyproject.toml": {
                "content": """
[project]
dependencies = ["openai", "httpx>=0.27"]

[project.optional-dependencies]
watch = ["watchdog"]
dev = ["pytest", "ruff"]
"""
            },
            "requirements.txt": {"content": "pyyaml\n# comment\npathspec\n"},
        }

        deps = collect_dependencies(files)

        self.assertIn("openai", deps)
        self.assertIn("httpx>=0.27", deps)
        self.assertIn("watchdog [watch]", deps)
        self.assertIn("pytest [dev]", deps)
        self.assertIn("pyyaml", deps)
        self.assertIn("pathspec", deps)

    def test_collect_test_info_detects_pytest_command_from_pep621(self):
        files = {
            "pyproject.toml": {
                "content": """
[project]
dependencies = ["openai"]

[project.optional-dependencies]
dev = ["pytest", "ruff"]
"""
            },
            "tests/test_app.py": {"content": "def test_app(): pass"},
        }

        test_paths, commands = collect_test_info(files)

        self.assertEqual(test_paths, ["tests/test_app.py"])
        self.assertIn("pytest -q", commands)


if __name__ == "__main__":
    unittest.main()
