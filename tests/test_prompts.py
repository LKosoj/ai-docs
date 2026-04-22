import asyncio
import tempfile
import unittest
from pathlib import Path

from ai_docs.prompts import (
    PromptStore,
    active,
    configure,
    load_prompt_overrides,
)
from ai_docs.summary import summarize_file_outputs


class PromptStoreTests(unittest.TestCase):
    def test_defaults_returned_when_no_override(self):
        store = PromptStore()
        self.assertIn("Markdown", store.summary())
        self.assertIn("Doxygen", store.module_summary_bundle())
        self.assertIn("overview_summary", store.module_summary_bundle())

    def test_override_replaces_default(self):
        store = PromptStore({"summary": "Custom summary prompt."})
        self.assertEqual(store.summary(), "Custom summary prompt.")
        self.assertIn("Doxygen", store.module_summary_bundle())

    def test_unknown_key_without_override_raises(self):
        store = PromptStore()
        with self.assertRaises(KeyError):
            store.get("unknown_prompt")

    def test_module_summary_override_propagates_to_bundle(self):
        store = PromptStore({"module_summary": "Custom module prompt body."})
        bundle = store.module_summary_bundle()
        self.assertIn("Custom module prompt body.", bundle)
        self.assertIn("<module_summary>", bundle)


class LoadPromptOverridesTests(unittest.TestCase):
    def test_reads_prompts_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".ai-docs.yaml"
            cfg.write_text(
                "prompts:\n  summary: |\n    My summary\n  module_summary: My module\n",
                encoding="utf-8",
            )
            result = load_prompt_overrides(Path(tmp))
            self.assertEqual(result["summary"], "My summary")
            self.assertEqual(result["module_summary"], "My module")

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_prompt_overrides(Path(tmp)), {})

    def test_invalid_yaml_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".ai-docs.yaml"
            cfg.write_text(":::not yaml:::", encoding="utf-8")
            self.assertEqual(load_prompt_overrides(Path(tmp)), {})

    def test_ignores_non_string_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".ai-docs.yaml"
            cfg.write_text("prompts:\n  summary: 42\n  module_summary: \"ok\"\n", encoding="utf-8")
            result = load_prompt_overrides(Path(tmp))
            self.assertNotIn("summary", result)
            self.assertEqual(result["module_summary"], "ok")


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.model = "gpt-4o-mini"
        self.calls = []

    async def chat(self, messages, cache=None):
        self.calls.append(messages)
        return self.responses.pop(0)


class SummaryUsesActiveStoreTests(unittest.TestCase):
    def tearDown(self):
        configure({})

    def test_summary_request_uses_overridden_prompt(self):
        configure({"summary": "MY CUSTOM SUMMARY PROMPT"})
        llm = FakeLLM(["just summary"])
        asyncio.run(
            summarize_file_outputs(
                "print('hi')",
                "code",
                [],
                llm,
                {},
                llm.model,
            )
        )
        system_prompt = llm.calls[0][0]["content"]
        self.assertIn("MY CUSTOM SUMMARY PROMPT", system_prompt)

    def test_active_returns_store_after_configure(self):
        configure({"summary": "abc"})
        self.assertEqual(active().summary(), "abc")


if __name__ == "__main__":
    unittest.main()
