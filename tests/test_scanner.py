import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_docs.scanner as scanner_module
from ai_docs.domain_rules import FIXED_INCLUDE_PATTERNS
from ai_docs.generator_cache import build_file_map
from ai_docs.scanner import scan_source


class ScannerTests(unittest.TestCase):
    def test_scan_local_dir_preserves_case_and_dockerfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print('hi')", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM python:3.11", encoding="utf-8")
            case_dir = root / "Src"
            case_dir.mkdir()
            (case_dir / "CaseSensitive.py").write_text("print('case')", encoding="utf-8")
            (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
            (root / ".build_ignore").write_text("build/**\n", encoding="utf-8")
            (root / "ignored.txt").write_text("secret", encoding="utf-8")
            (root / "build" / "ignored.py").parent.mkdir(parents=True, exist_ok=True)
            (root / "build" / "ignored.py").write_text("print('no')", encoding="utf-8")
            node_modules_dir = root / "node_modules" / "pkg"
            node_modules_dir.mkdir(parents=True)
            (node_modules_dir / "ignored.py").write_text("print('no')", encoding="utf-8")

            result = scan_source(str(root), workers=2)
            paths = {f["path"] for f in result.files}
            self.assertIn("app.py", paths)
            self.assertIn("Dockerfile", paths)
            self.assertIn("Src/CaseSensitive.py", paths)
            self.assertNotIn("ignored.txt", paths)
            self.assertNotIn("build/ignored.py", paths)
            self.assertNotIn("node_modules/pkg/ignored.py", paths)

    def test_scan_prunes_heavy_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print('hi')", encoding="utf-8")
            heavy_dir = root / "node_modules" / "pkg"
            heavy_dir.mkdir(parents=True)
            (heavy_dir / "ignored.py").write_text("print('no')", encoding="utf-8")
            seen_root_dirnames = None

            original_walk = scanner_module.os.walk

            def recording_walk(*args, **kwargs):
                nonlocal seen_root_dirnames
                for dirpath, dirnames, filenames in original_walk(*args, **kwargs):
                    if Path(dirpath) == root:
                        seen_root_dirnames = dirnames
                    yield dirpath, dirnames, filenames

            with patch("ai_docs.scanner.os.walk", side_effect=recording_walk):
                result = scan_source(str(root), workers=1)

            paths = {f["path"] for f in result.files}
            self.assertIn("app.py", paths)
            self.assertNotIn("node_modules/pkg/ignored.py", paths)
            self.assertIsNotNone(seen_root_dirnames)
            self.assertNotIn("node_modules", seen_root_dirnames)

    def test_scan_does_not_create_default_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print('hi')", encoding="utf-8")

            scan_source(str(root), workers=1)

            self.assertFalse((root / ".ai-docs.yaml").exists())

    def test_scan_includes_github_workflows_as_ci(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = root / ".github" / "workflows" / "build.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: ci\non: [push]\njobs: {}\n", encoding="utf-8")

            result = scan_source(str(root), workers=1)
            records = {f["path"]: f for f in result.files}

            self.assertIn(".github/workflows/build.yml", records)
            self.assertEqual(records[".github/workflows/build.yml"]["type"], "ci")
            self.assertIn("ci", records[".github/workflows/build.yml"]["domains"])

    def test_scan_hash_uses_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "first.py").write_bytes(b"\xffprint(1)\n")
            (root / "second.py").write_bytes(b"\xfeprint(1)\n")

            result = scan_source(str(root), workers=1)
            records = {f["path"]: f for f in result.files}

            self.assertEqual(records["first.py"]["content"], records["second.py"]["content"])
            self.assertNotEqual(records["first.py"]["hash"], records["second.py"]["hash"])
            self.assertIn("decode_error", records["first.py"])
            self.assertIn("invalid bytes ignored", records["first.py"]["decode_error"])
            file_map = build_file_map(result.files)
            self.assertIn("decode_error", file_map["first.py"])

    def test_scanner_uses_shared_fixed_include_patterns(self):
        self.assertIs(scanner_module.FIXED_INCLUDE_PATTERNS, FIXED_INCLUDE_PATTERNS)
        self.assertIn(".gitlab-ci.yml", scanner_module.FIXED_INCLUDE_PATTERNS)


if __name__ == "__main__":
    unittest.main()
