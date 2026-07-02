import tempfile
import unittest
from pathlib import Path

from ai_docs.config import ConfigError, load_extension_config


class ConfigTests(unittest.TestCase):
    def _defaults(self):
        return {
            "code_extensions": {".py": "Python"},
            "doc_extensions": {".md": "Markdown"},
            "config_extensions": {".toml": "TOML"},
        }

    def test_missing_config_returns_defaults_without_writing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            config = load_extension_config(root, self._defaults())

            self.assertEqual(config["code_extensions"], {".py": "Python"})
            self.assertEqual(config["exclude"], set())
            self.assertFalse((root / ".ai-docs.yaml").exists())

    def test_rejects_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-docs.yaml").write_text("code_extensions: [", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_extension_config(root, self._defaults())

    def test_rejects_wrong_exclude_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-docs.yaml").write_text("exclude: '*.log'\n", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_extension_config(root, self._defaults())


if __name__ == "__main__":
    unittest.main()
