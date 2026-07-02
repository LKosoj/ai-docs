import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_docs.cli import parse_args


class ParseArgsTests(unittest.TestCase):
    def test_backward_compat_no_subcommand(self):
        args = parse_args(["--source", ".", "--mkdocs"])
        self.assertEqual(args.command, "gen")
        self.assertEqual(args.source, ".")
        self.assertTrue(args.mkdocs)

    def test_explicit_gen_subcommand(self):
        args = parse_args(["gen", "--source", ".", "--readme"])
        self.assertEqual(args.command, "gen")
        self.assertTrue(args.readme)

    def test_lint_subcommand(self):
        args = parse_args(["lint", "--source", "."])
        self.assertEqual(args.command, "lint")
        self.assertFalse(args.quiet)

    def test_lint_with_quiet(self):
        args = parse_args(["lint", "--source", ".", "--quiet"])
        self.assertTrue(args.quiet)

    def test_prdiff_default_base_is_main(self):
        args = parse_args(["pr-diff", "--source", "."])
        self.assertEqual(args.command, "pr-diff")
        self.assertEqual(args.base, "main")

    def test_prdiff_custom_base(self):
        args = parse_args(["pr-diff", "--source", ".", "--base", "develop"])
        self.assertEqual(args.base, "develop")

    def test_watch_default_debounce(self):
        args = parse_args(["watch", "--source", "."])
        self.assertEqual(args.command, "watch")
        self.assertAlmostEqual(args.debounce, 2.0)

    def test_module_entrypoint_preserves_lint_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("print(1)\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "ai_docs", "lint", "--source", str(root)],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("index not found", result.stdout)


class LintCommandTests(unittest.TestCase):
    def _make_args(self, source: Path, cache_dir: str = ".ai_docs_cache") -> object:
        import argparse
        ns = argparse.Namespace(
            source=str(source),
            include=None,
            exclude=None,
            max_size=200_000,
            threads=1,
            cache_dir=cache_dir,
            quiet=False,
        )
        return ns

    def test_missing_index_returns_rc_2(self):
        from ai_docs.cli_lint import run_lint
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("print(1)", encoding="utf-8")
            rc = run_lint(self._make_args(root))
            self.assertEqual(rc, 2)

    def test_clean_state_returns_0(self):
        from ai_docs.cli_lint import run_lint
        from ai_docs.cache import CacheManager
        from ai_docs.generator_cache import build_file_map
        from ai_docs.scanner import scan_source

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("print(1)\n", encoding="utf-8")
            scan = scan_source(str(root), workers=1)
            cache_dir = root / ".ai_docs_cache"
            cache = CacheManager(cache_dir)
            cache.save_index({"files": build_file_map(scan.files), "sections": {}})

            rc = run_lint(self._make_args(root))
            self.assertEqual(rc, 0)

    def test_modified_file_returns_rc_1(self):
        from ai_docs.cli_lint import run_lint
        from ai_docs.cache import CacheManager
        from ai_docs.generator_cache import build_file_map
        from ai_docs.scanner import scan_source

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("print(1)\n", encoding="utf-8")
            scan = scan_source(str(root), workers=1)
            cache_dir = root / ".ai_docs_cache"
            cache = CacheManager(cache_dir)
            cache.save_index({"files": build_file_map(scan.files), "sections": {}})

            (root / "a.py").write_text("print(2)\n", encoding="utf-8")
            rc = run_lint(self._make_args(root))
            self.assertEqual(rc, 1)


class PrDiffCommandTests(unittest.TestCase):
    def _make_args(self, source: Path, base: str = "main", include=None, exclude=None) -> object:
        import argparse
        return argparse.Namespace(
            source=str(source),
            include=include,
            exclude=exclude,
            max_size=200_000,
            threads=1,
            cache_dir=".ai_docs_cache",
            output=None,
            base=base,
            language="ru",
            mkdocs=False,
            readme=False,
            no_cache=True,
            local_site=False,
        )

    def test_non_git_source_returns_rc_2(self):
        from ai_docs.cli_prdiff import run_prdiff
        with tempfile.TemporaryDirectory() as tmp:
            rc = run_prdiff(self._make_args(Path(tmp)))
            self.assertEqual(rc, 2)

    def test_url_source_returns_rc_2(self):
        from ai_docs.cli_prdiff import run_prdiff
        import argparse
        ns = argparse.Namespace(
            source="https://example.com/repo.git",
            include=None,
            exclude=None,
            max_size=200_000,
            threads=1,
            cache_dir=".ai_docs_cache",
            output=None,
            base="main",
            language="ru",
            mkdocs=False,
            readme=False,
            no_cache=True,
            local_site=False,
        )
        rc = run_prdiff(ns)
        self.assertEqual(rc, 2)

    def test_prdiff_uses_full_scan_and_changed_mask(self):
        from ai_docs.cli_prdiff import run_prdiff

        def git(root: Path, *args: str) -> None:
            subprocess.run(
                ["git", "-C", str(root), *args],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "checkout", "-b", "main")
            (root / "a.py").write_text("print(1)\n", encoding="utf-8")
            (root / "b.py").write_text("print(2)\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init")
            git(root, "checkout", "-b", "feature")
            (root / "a.py").write_text("print(3)\n", encoding="utf-8")
            git(root, "add", "a.py")
            git(root, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "change a")

            with patch("ai_docs.cli_prdiff.from_env", return_value=object()), \
                 patch("ai_docs.cli_prdiff.generate_docs") as generate:
                rc = run_prdiff(self._make_args(root))

        self.assertEqual(rc, 0)
        kwargs = generate.call_args.kwargs
        self.assertEqual({item["path"] for item in kwargs["files"]}, {"a.py", "b.py"})
        self.assertEqual(kwargs["changed_paths"], {"a.py"})
        self.assertEqual(kwargs["deleted_paths"], set())

    def test_prdiff_filters_deleted_paths_outside_scan_scope(self):
        from ai_docs.cli_prdiff import run_prdiff

        def git(root: Path, *args: str) -> None:
            subprocess.run(
                ["git", "-C", str(root), *args],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "checkout", "-b", "main")
            (root / "a.py").write_text("print(1)\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "old.md").write_text("old\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init")
            git(root, "checkout", "-b", "feature")
            (root / "a.py").write_text("print(2)\n", encoding="utf-8")
            (root / "docs" / "old.md").unlink()
            git(root, "add", "-A")
            git(root, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "change")

            with patch("ai_docs.cli_prdiff.from_env", return_value=object()), \
                 patch("ai_docs.cli_prdiff.generate_docs") as generate:
                rc = run_prdiff(self._make_args(root, include=["*.py"]))

        self.assertEqual(rc, 0)
        kwargs = generate.call_args.kwargs
        self.assertEqual(kwargs["changed_paths"], {"a.py"})
        self.assertEqual(kwargs["deleted_paths"], set())


if __name__ == "__main__":
    unittest.main()
