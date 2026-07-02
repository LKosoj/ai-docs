import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_docs.generator_shared import get_cached_text
from ai_docs.summary import _needs_doxygen_fix, summarize_file_outputs, write_summary


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.model = "gpt-4o-mini"
        self.context_limit = 1000
        self.max_tokens = 200
        self.calls = []

    async def chat(self, messages, cache=None):
        self.calls.append(messages)
        return self.responses.pop(0)


class SummaryTests(unittest.TestCase):
    def test_needs_doxygen_fix_handles_single_digit_line(self):
        self.assertFalse(_needs_doxygen_fix("Summary\n5"))

    def test_needs_doxygen_fix_detects_numbered_list(self):
        self.assertTrue(_needs_doxygen_fix("Summary\n1. пункт"))
        self.assertTrue(_needs_doxygen_fix("Summary\n10. пункт"))

    def test_code_summary_reuses_module_intro(self):
        llm = FakeLLM(
            [
                "<overview_summary>Short intro.</overview_summary><module_summary>Module intro.\n\nfunc()\nDoes thing.</module_summary>",
            ]
        )
        outputs = asyncio.run(
            summarize_file_outputs(
                "print('hi')",
                "code",
                [],
                llm,
                {},
                llm.model,
                include_module_summary=True,
            )
        )
        self.assertEqual(outputs["summary"], "Short intro.")
        self.assertIn("func()", outputs["module_summary"])
        self.assertEqual(len(llm.calls), 1)

    def test_empty_code_file_returns_deterministic_module_summary(self):
        llm = FakeLLM([])

        outputs = asyncio.run(
            summarize_file_outputs(
                "",
                "code",
                [],
                llm,
                {},
                llm.model,
                include_module_summary=True,
            )
        )

        self.assertEqual(outputs["summary"], "Пустой файл без исполняемого содержимого.")
        self.assertIn("Файл пустой", outputs["module_summary"])
        self.assertEqual(llm.calls, [])

    def test_empty_config_file_returns_deterministic_config_summary(self):
        llm = FakeLLM([])

        outputs = asyncio.run(
            summarize_file_outputs(
                "  \n",
                "config",
                [],
                llm,
                {},
                llm.model,
                include_config_summary=True,
            )
        )

        self.assertEqual(outputs["summary"], "Пустой конфигурационный файл без заданных параметров.")
        self.assertIn("Файл пустой", outputs["config_summary"])
        self.assertEqual(llm.calls, [])

    def test_multichunk_module_summary_combines_chunks(self):
        llm = FakeLLM(
            [
                "<overview_summary>Chunk one intro.</overview_summary><module_summary>fn_one()</module_summary>",
                "<overview_summary>Chunk two intro.</overview_summary><module_summary>fn_two()</module_summary>",
                "<overview_summary>Combined short intro.</overview_summary><module_summary>Combined intro.\n\nfn_one()\n---\nfn_two()</module_summary>",
                "Combined intro.\n\nfn_one()\n---\nfn_two()",
            ]
        )
        with patch("ai_docs.summary.chunk_text", return_value=["chunk-one", "chunk-two"]):
            outputs = asyncio.run(
                summarize_file_outputs(
                    "long file",
                    "code",
                    [],
                    llm,
                    {},
                    llm.model,
                    include_module_summary=True,
                )
            )
        self.assertEqual(outputs["summary"], "Combined short intro.")
        self.assertIn("fn_two()", outputs["module_summary"])
        self.assertEqual(len(llm.calls), 4)

    def test_summary_chunk_size_uses_llm_budget(self):
        llm = FakeLLM(["summary"])
        with patch("ai_docs.summary.chunk_text", return_value=["chunk"]) as chunk_text:
            outputs = asyncio.run(
                summarize_file_outputs(
                    "long file",
                    "docs",
                    [],
                    llm,
                    {},
                    llm.model,
                )
            )

        self.assertEqual(outputs["summary"], "summary")
        self.assertEqual(chunk_text.call_args.kwargs["max_tokens"], 600)

    def test_missing_module_summary_tag_fails_explicitly(self):
        llm = FakeLLM(["<overview_summary>Short intro.</overview_summary>"])

        with self.assertRaises(RuntimeError) as raised:
            asyncio.run(
                summarize_file_outputs(
                    "print('hi')",
                    "code",
                    [],
                    llm,
                    {},
                    llm.model,
                    include_module_summary=True,
                )
            )

        self.assertIn("module_summary", str(raised.exception))

    def test_missing_config_summary_tag_fails_explicitly(self):
        llm = FakeLLM(["<overview_summary>Short intro.</overview_summary>"])

        with self.assertRaises(RuntimeError) as raised:
            asyncio.run(
                summarize_file_outputs(
                    "x: 1",
                    "config",
                    [],
                    llm,
                    {},
                    llm.model,
                    include_config_summary=True,
                )
            )

        self.assertIn("config_summary", str(raised.exception))

    def test_summary_text_is_memoized_in_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.md"
            path.write_text("cached summary", encoding="utf-8")
            meta = {"summary_path": str(path)}
            self.assertEqual(get_cached_text(meta, "summary_path", "summary_text"), "cached summary")
            path.unlink()
            self.assertEqual(get_cached_text(meta, "summary_path", "summary_text"), "cached summary")

    def test_write_summary_preserves_case_sensitive_uniqueness(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary_dir = Path(tmp)
            first = write_summary(summary_dir, "Src/A.py", "one")
            second = write_summary(summary_dir, "src/a.py", "two")
            self.assertNotEqual(first.name, second.name)
            self.assertEqual(first.read_text(encoding="utf-8"), "one")
            self.assertEqual(second.read_text(encoding="utf-8"), "two")


if __name__ == "__main__":
    unittest.main()
