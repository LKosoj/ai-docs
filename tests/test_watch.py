import tempfile
import threading
import time
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from ai_docs.cli_watch import _Debouncer, should_watch_path


class WatchDebouncerTests(unittest.TestCase):
    def test_events_during_running_regen_schedule_one_followup_without_overlap(self):
        lock = threading.Lock()
        first_started = threading.Event()
        release_first = threading.Event()
        second_done = threading.Event()
        errors = []
        calls = 0
        active = 0
        peak_active = 0

        def regenerate():
            nonlocal calls, active, peak_active
            with lock:
                calls += 1
                call_no = calls
                active += 1
                peak_active = max(peak_active, active)
            try:
                if call_no == 1:
                    first_started.set()
                    if not release_first.wait(2.0):
                        errors.append("first regeneration was not released")
                else:
                    second_done.set()
            finally:
                with lock:
                    active -= 1

        debouncer = _Debouncer(0.01, regenerate)
        try:
            debouncer.bump()
            self.assertTrue(first_started.wait(1.0))
            debouncer.bump()
            debouncer.bump()
            debouncer.bump()
            time.sleep(0.03)
            release_first.set()
            self.assertTrue(second_done.wait(1.0))
            time.sleep(0.05)
        finally:
            debouncer.cancel()

        self.assertEqual(errors, [])
        with lock:
            self.assertEqual(calls, 2)
            self.assertEqual(peak_active, 1)

    def test_regeneration_failure_is_reported_on_stderr(self):
        done = threading.Event()

        def regenerate():
            done.set()
            raise RuntimeError("boom")

        debouncer = _Debouncer(0.01, regenerate)
        try:
            with patch("sys.stdout", new_callable=StringIO) as stdout, \
                 patch("sys.stderr", new_callable=StringIO) as stderr:
                debouncer.bump()
                self.assertTrue(done.wait(1.0))
                time.sleep(0.05)
        finally:
            debouncer.cancel()

        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("[ai-docs watch] regeneration failed: boom", stderr.getvalue())


class WatchEventFilterTests(unittest.TestCase):
    def test_generated_artifacts_under_source_output_do_not_trigger_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            ignored = [
                root / "mkdocs.yml",
                root / ".ai-docs" / "overview.md",
                root / "ai_docs_site" / "index.html",
                root / ".ai_docs_cache" / "index.json",
            ]
            for path in ignored:
                with self.subTest(path=path):
                    self.assertFalse(should_watch_path(path, root, root, ".ai_docs_cache"))

            self.assertTrue(should_watch_path(root / "src" / "app.py", root, root, ".ai_docs_cache"))
            self.assertTrue(should_watch_path(root / "README.md", root, root, ".ai_docs_cache"))
            self.assertFalse(
                should_watch_path(
                    root / "README.md",
                    root,
                    root,
                    ".ai_docs_cache",
                    ignore_readme=True,
                )
            )

    def test_generated_artifacts_are_filtered_relative_to_output_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            output_root = root / "docs-output"

            self.assertTrue(should_watch_path(root / "cache" / "source.py", root, output_root, "cache"))

            ignored = [
                output_root / "mkdocs.yml",
                output_root / ".ai-docs" / "overview.md",
                output_root / "ai_docs_site" / "index.html",
                output_root / "cache" / "index.json",
            ]
            for path in ignored:
                with self.subTest(path=path):
                    self.assertFalse(should_watch_path(path, root, output_root, "cache"))

    def test_nested_cache_artifacts_do_not_trigger_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            self.assertFalse(
                should_watch_path(
                    root / "cache" / "nested" / "llm_cache.json",
                    root,
                    root,
                    root / "cache" / "nested",
                )
            )
            self.assertTrue(
                should_watch_path(
                    root / "cache" / "source.py",
                    root,
                    root,
                    root / "cache" / "nested",
                )
            )

    def test_github_workflows_are_watched_but_hidden_service_dirs_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()

            self.assertTrue(
                should_watch_path(root / ".github" / "workflows" / "build.yml", root, root, ".ai_docs_cache")
            )

            ignored = [
                root / ".git" / "config",
                root / ".pytest_cache" / "v" / "cache" / "nodeids",
                root / ".vscode" / "settings.json",
            ]
            for path in ignored:
                with self.subTest(path=path):
                    self.assertFalse(should_watch_path(path, root, root, ".ai_docs_cache"))

    def test_paths_outside_source_do_not_trigger_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()

            self.assertFalse(
                should_watch_path(
                    base / "other" / "app.py",
                    base / "source",
                    base / "source",
                    ".ai_docs_cache",
                )
            )


if __name__ == "__main__":
    unittest.main()
