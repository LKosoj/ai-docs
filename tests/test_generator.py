import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ai_docs.generation_config import GenerationConfig
from ai_docs.generator import GenerationError, generate_docs, generate_docs_async


class FakeLLM:
    model = "gpt-test"
    max_tokens = 100
    context_limit = 1000

    async def chat(self, messages, cache=None):
        return "ok"


class FailingLLM(FakeLLM):
    async def chat(self, messages, cache=None):
        raise RuntimeError("boom")


def _source_file() -> dict:
    return {
        "path": "src/app.py",
        "content": "print(1)\n",
        "size": 9,
        "type": "code",
        "domains": [],
        "hash": "hash-app",
    }


class GenerateDocsApiTests(unittest.TestCase):
    def test_generate_docs_async_is_public_api(self):
        build_sections = AsyncMock(
            return_value=(
                {"index.md": "# Index\n"},
                {},
                {},
                [],
                [],
                {},
                [],
                "overview",
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = GenerationConfig(
                source_url="https://example.com/src/",
                force_sections={"configs"},
                regen_all_threshold=0,
            )

            with patch.dict(os.environ, {"AI_DOCS_REGEN": "all"}), \
                 patch("ai_docs.generator.build_sections", build_sections), \
                 patch("ai_docs.generator.write_docs") as write_docs, \
                 patch("ai_docs.generator.build_mkdocs") as build_mkdocs:
                asyncio.run(
                    generate_docs_async(
                        files=[],
                        output_root=root,
                        cache_dir=root / ".cache",
                        llm=FakeLLM(),
                        language="ru",
                        write_readme_flag=False,
                        write_mkdocs=False,
                        generation_config=config,
                    )
                )

        build_sections.assert_awaited_once()
        build_kwargs = build_sections.call_args.kwargs
        self.assertEqual(build_kwargs["force_sections"], {"configs"})
        self.assertEqual(build_kwargs["source_url"], "https://example.com/src/")
        self.assertEqual(build_kwargs["regen_all_threshold"], 0)
        write_docs.assert_called_once()
        build_mkdocs.assert_called_once()

    def test_generate_docs_is_sync_wrapper_for_async_api(self):
        async_generate = AsyncMock(return_value=None)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("ai_docs.generator.generate_docs_async", async_generate):
                generate_docs(
                    files=[],
                    output_root=root,
                    cache_dir=root / ".cache",
                    llm=FakeLLM(),
                    language="ru",
                    write_readme_flag=False,
                    write_mkdocs=False,
                )

        async_generate.assert_awaited_once()

    def test_summarization_error_is_fatal_before_docs_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("ai_docs.generator.build_sections") as build_sections, \
                 patch("ai_docs.generator.write_docs") as write_docs, \
                 patch("ai_docs.generator.build_mkdocs") as build_mkdocs:
                with self.assertRaises(GenerationError) as raised:
                    asyncio.run(
                        generate_docs_async(
                            files=[_source_file()],
                            output_root=root,
                            cache_dir=root / ".cache",
                            llm=FailingLLM(),
                            language="ru",
                            write_readme_flag=False,
                            write_mkdocs=True,
                            use_cache=False,
                            threads=1,
                        )
                    )

        self.assertIn("src/app.py", str(raised.exception))
        self.assertIn("boom", str(raised.exception))
        build_sections.assert_not_called()
        write_docs.assert_not_called()
        build_mkdocs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
