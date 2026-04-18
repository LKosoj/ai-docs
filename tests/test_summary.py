import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_docs.generator_shared import get_cached_text
from ai_docs.summary import summarize_file_outputs, write_summary


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.model = "gpt-4o-mini"
        self.calls = []

    async def chat(self, messages, cache=None):
        self.calls.append(messages)
        return self.responses.pop(0)


class SummaryTests(unittest.TestCase):
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
