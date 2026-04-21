import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_docs.generator_cache import cleanup_orphan_summaries
from ai_docs.generator_summarize import summarize_entries
from ai_docs.summary import write_summary


class ParallelChunkLLM:
    """LLM stub that tracks concurrency of _summarize_chunks."""

    def __init__(self, model="gpt-4o-mini"):
        self.model = model
        self.active = 0
        self.max_active = 0
        self.call_count = 0

    async def chat(self, messages, cache=None):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.call_count += 1
        try:
            await asyncio.sleep(0.02)
            return "chunk summary"
        finally:
            self.active -= 1


class SummarizeChunkParallelism(unittest.TestCase):
    def test_summarize_chunks_run_concurrently(self):
        from ai_docs.summary import _summarize_chunks

        llm = ParallelChunkLLM()
        with patch("ai_docs.summary.chunk_text", return_value=["a", "b", "c", "d"]):
            result = asyncio.run(
                _summarize_chunks(
                    "content",
                    "prompt",
                    "combine",
                    llm,
                    {},
                    llm.model,
                )
            )
        self.assertTrue(result)
        # 4 chunk calls + 1 combine call
        self.assertEqual(llm.call_count, 5)
        # all 4 per-chunk requests should overlap
        self.assertGreaterEqual(llm.max_active, 4)


class DebouncedSaveCb(unittest.TestCase):
    def test_save_cb_is_batched(self):
        saves = []

        def save_cb():
            saves.append(1)

        llm = ParallelChunkLLM()
        items = [
            (f"src/file_{i}.py", {"content": "x", "type": "code", "domains": []})
            for i in range(25)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("ai_docs.summary.chunk_text", return_value=["one"]):
                asyncio.run(
                    summarize_entries(
                        items,
                        base / "files",
                        base / "modules",
                        base / "configs",
                        llm,
                        {},
                        threads=4,
                        save_cb=save_cb,
                        errors=[],
                        label="test",
                    )
                )
        # Previously save_cb would fire once per file (25). With batching it
        # must be strictly fewer than the file count and at least once.
        self.assertGreaterEqual(len(saves), 1)
        self.assertLess(len(saves), len(items))


class CleanupOrphanSummaries(unittest.TestCase):
    def test_cleanup_removes_only_unreferenced_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            summaries_dir = base / "files"
            modules_dir = base / "modules"
            configs_dir = base / "configs"
            for d in (summaries_dir, modules_dir, configs_dir):
                d.mkdir(parents=True)

            keep = write_summary(summaries_dir, "src/a.py", "keep")
            orphan = write_summary(summaries_dir, "src/b.py", "orphan")
            module_keep = write_summary(modules_dir, "src/a.py", "mod")
            (modules_dir / "legacy.md").write_text("legacy", encoding="utf-8")

            file_map = {
                "src/a.py": {
                    "summary_path": str(keep),
                    "module_summary_path": str(module_keep),
                }
            }
            cleanup_orphan_summaries(file_map, summaries_dir, modules_dir, configs_dir)

            self.assertTrue(keep.exists())
            self.assertTrue(module_keep.exists())
            self.assertFalse(orphan.exists())
            self.assertFalse((modules_dir / "legacy.md").exists())


class MermaidPostprocessFast(unittest.TestCase):
    def test_skips_files_without_mermaid(self):
        from ai_docs.generator_output import _postprocess_mermaid_html

        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            plain = site / "plain.html"
            plain.write_text("<html>no diagram &gt; here</html>", encoding="utf-8")
            mermaid_page = site / "arch.html"
            mermaid_page.write_text(
                '<html><div class="mermaid">A --&gt; B</div></html>',
                encoding="utf-8",
            )
            _postprocess_mermaid_html(site)

            # plain files must not be touched
            self.assertEqual(plain.read_text(encoding="utf-8"), "<html>no diagram &gt; here</html>")
            # mermaid files get &gt; -> >
            self.assertIn("A --> B", mermaid_page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
