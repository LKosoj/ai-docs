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


class LLMClientGlobalConcurrency(unittest.TestCase):
    def test_llm_client_caps_concurrent_requests(self):
        from ai_docs.llm import LLMClient

        client = LLMClient(
            api_key="test",
            base_url="",
            model="gpt-4o-mini",
            concurrency=3,
        )

        active = 0
        peak = 0
        lock = asyncio.Lock()

        class FakeCompletions:
            async def create(self, **kwargs):
                nonlocal active, peak
                async with lock:
                    active += 1
                    peak = max(peak, active)
                try:
                    await asyncio.sleep(0.02)
                    class _Msg:
                        content = "ok"
                    class _Choice:
                        message = _Msg()
                    class _Resp:
                        choices = [_Choice()]
                    return _Resp()
                finally:
                    async with lock:
                        active -= 1

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        client._client = FakeClient()

        async def run_many():
            # 20 independent requests with unique messages (no cache hits)
            await asyncio.gather(
                *(
                    client.chat([{"role": "user", "content": f"req-{i}"}])
                    for i in range(20)
                )
            )

        asyncio.run(run_many())
        self.assertLessEqual(peak, 3)
        self.assertGreaterEqual(peak, 1)

    def test_cache_hit_does_not_consume_slot(self):
        from ai_docs.llm import LLMClient

        client = LLMClient(
            api_key="test",
            base_url="",
            model="gpt-4o-mini",
            concurrency=1,
        )

        call_count = 0

        class FakeCompletions:
            async def create(self, **kwargs):
                nonlocal call_count
                call_count += 1

                class _Msg:
                    content = "first"

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        client._client = FakeClient()

        async def scenario():
            cache: Dict[str, str] = {}
            messages = [{"role": "user", "content": "hello"}]
            # First call: cache miss, network goes through semaphore
            first = await client.chat(messages, cache=cache)
            # Concurrent cache hits must not block even with concurrency=1
            second, third = await asyncio.gather(
                client.chat(messages, cache=cache),
                client.chat(messages, cache=cache),
            )
            return first, second, third, call_count

        from typing import Dict  # local import to avoid polluting module scope

        first, second, third, count = asyncio.run(scenario())
        self.assertEqual(first, "first")
        self.assertEqual(second, "first")
        self.assertEqual(third, "first")
        self.assertEqual(count, 1)


class BuildSectionsParallelism(unittest.TestCase):
    def _run_build_sections(self, concurrency: int, threads: int):
        from ai_docs.generator_sections import build_sections
        from ai_docs.llm import LLMClient

        active = 0
        max_active = 0
        call_count = 0
        lock = asyncio.Lock()

        class FakeCompletions:
            async def create(self, **kwargs):
                nonlocal active, max_active, call_count
                async with lock:
                    active += 1
                    max_active = max(max_active, active)
                    call_count += 1
                try:
                    await asyncio.sleep(0.02)

                    class _Msg:
                        content = "generated content"

                    class _Choice:
                        message = _Msg()

                    class _Resp:
                        choices = [_Choice()]

                    return _Resp()
                finally:
                    async with lock:
                        active -= 1

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        llm = LLMClient(
            api_key="test",
            base_url="",
            model="gpt-4o-mini",
            concurrency=concurrency,
        )
        llm._client = FakeClient()

        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / ".ai-docs"

            file_map = {}
            for i in range(3):
                summary = write_summary(Path(tmp) / "sums", f"src/mod_{i}.py", f"summary {i}")
                module_summary = write_summary(Path(tmp) / "mods", f"src/mod_{i}.py", f"mod {i}")
                file_map[f"src/mod_{i}.py"] = {
                    "type": "code",
                    "domains": [],
                    "summary_path": str(summary),
                    "module_summary_path": str(module_summary),
                }

            added = {"src/mod_0.py": file_map["src/mod_0.py"]}

            with patch("ai_docs.generator_sections.count_tokens", return_value=100000), \
                 patch("ai_docs.generator_sections.chunk_text",
                       side_effect=lambda text, model, max_tokens: [text]):
                asyncio.run(
                    build_sections(
                        file_map,
                        added,
                        {},
                        {},
                        docs_dir,
                        llm,
                        {},
                        "ru",
                        threads=threads,
                        input_budget=2000,
                        force_sections={"all"},
                    )
                )

        return call_count, max_active

    def test_build_sections_runs_contexts_and_tasks_concurrently(self):
        call_count, max_active = self._run_build_sections(concurrency=8, threads=8)
        self.assertGreater(call_count, 4)
        self.assertGreaterEqual(max_active, 3)

    def test_build_sections_respects_global_llm_concurrency_cap(self):
        # With threads=5 → LLMClient.concurrency=5 → no matter how many
        # coroutines gather, the network layer must never exceed 5 in-flight.
        call_count, max_active = self._run_build_sections(concurrency=5, threads=5)
        self.assertGreater(call_count, 4)
        self.assertLessEqual(max_active, 5)

    def test_single_thread_serializes_llm_calls(self):
        call_count, max_active = self._run_build_sections(concurrency=1, threads=1)
        self.assertGreater(call_count, 4)
        self.assertEqual(max_active, 1)


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
