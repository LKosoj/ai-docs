import tempfile
import unittest
from pathlib import Path

from ai_docs.config import ConfigError
from ai_docs.site_config import (
    active_source_url,
    configure_source_url,
    format_citation,
    load_source_url,
)


class LoadSourceUrlTests(unittest.TestCase):
    def test_missing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_source_url(Path(tmp)))

    def test_reads_value_with_trailing_slash_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".ai-docs.yaml"
            cfg.write_text(
                "source_url: https://gitlab.example.com/group/repo/-/blob/main\n",
                encoding="utf-8",
            )
            self.assertEqual(
                load_source_url(Path(tmp)),
                "https://gitlab.example.com/group/repo/-/blob/main/",
            )

    def test_rejects_non_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".ai-docs.yaml"
            cfg.write_text("source_url: 42\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_source_url(Path(tmp))

    def test_rejects_broken_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".ai-docs.yaml"
            cfg.write_text("source_url: [", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_source_url(Path(tmp))


class FormatCitationTests(unittest.TestCase):
    def test_no_url_produces_plain_text(self):
        self.assertEqual(
            format_citation("ai_docs/cli.py", None),
            "*Источник:* `ai_docs/cli.py`",
        )

    def test_with_url_produces_link(self):
        citation = format_citation(
            "ai_docs/cli.py", "https://github.com/u/r/blob/main/"
        )
        self.assertIn("[`ai_docs/cli.py`]", citation)
        self.assertIn("https://github.com/u/r/blob/main/ai_docs/cli.py", citation)

    def test_normalizes_backslashes(self):
        citation = format_citation("ai_docs\\cli.py", None)
        self.assertIn("`ai_docs/cli.py`", citation)


class ActiveSourceUrlTests(unittest.TestCase):
    def tearDown(self):
        configure_source_url(None)

    def test_configure_and_read(self):
        configure_source_url("https://example.com/")
        self.assertEqual(active_source_url(), "https://example.com/")

    def test_reset_to_none(self):
        configure_source_url("https://example.com/")
        configure_source_url(None)
        self.assertIsNone(active_source_url())


if __name__ == "__main__":
    unittest.main()
