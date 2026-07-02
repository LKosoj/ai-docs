import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_docs.scanner as scanner_module
from ai_docs.domain_rules import FIXED_INCLUDE_PATTERNS
from ai_docs.generator_cache import build_file_map
from ai_docs.scanner import build_scan_scope, path_in_scan_scope, scan_source


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

    def test_scan_keeps_application_code_with_ambiguous_infra_markers_as_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "app/tasks/worker.py": "def run():\n    return None\n",
                "app/gateway/api.py": "def handler():\n    return None\n",
                "src/s3util/helper.py": "def build_key():\n    return 'key'\n",
            }
            for rel_path, content in files.items():
                path = root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            result = scan_source(str(root), workers=1)
            records = {f["path"]: f for f in result.files}

            self.assertEqual(records["app/tasks/worker.py"]["type"], "code")
            self.assertNotIn("ansible", records["app/tasks/worker.py"]["domains"])
            self.assertEqual(records["app/gateway/api.py"]["type"], "code")
            self.assertNotIn("service_mesh", records["app/gateway/api.py"]["domains"])
            self.assertEqual(records["src/s3util/helper.py"]["type"], "code")
            self.assertNotIn("data_storage", records["src/s3util/helper.py"]["domains"])

    def test_scan_preserves_real_infra_and_ci_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = root / ".github" / "workflows" / "build.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: ci\non: [push]\njobs: {}\n", encoding="utf-8")
            k8s = root / "deploy" / "k8s" / "deployment.yaml"
            k8s.parent.mkdir(parents=True)
            k8s.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")
            ansible = root / "roles" / "web" / "tasks" / "main.yml"
            ansible.parent.mkdir(parents=True)
            ansible.write_text("- name: install\n  apt:\n    name: nginx\n", encoding="utf-8")
            ansible_defaults = root / "roles" / "web" / "defaults" / "main.yml"
            ansible_defaults.parent.mkdir(parents=True)
            ansible_defaults.write_text("nginx_port: 80\n", encoding="utf-8")
            storage = root / "infra" / "s3" / "bucket.yaml"
            storage.parent.mkdir(parents=True)
            storage.write_text("bucket: docs\n", encoding="utf-8")

            result = scan_source(str(root), workers=1)
            records = {f["path"]: f for f in result.files}

            self.assertEqual(records[".github/workflows/build.yml"]["type"], "ci")
            self.assertIn("ci", records[".github/workflows/build.yml"]["domains"])
            self.assertEqual(records["deploy/k8s/deployment.yaml"]["type"], "infra")
            self.assertIn("kubernetes", records["deploy/k8s/deployment.yaml"]["domains"])
            self.assertEqual(records["roles/web/tasks/main.yml"]["type"], "infra")
            self.assertIn("ansible", records["roles/web/tasks/main.yml"]["domains"])
            self.assertEqual(records["roles/web/defaults/main.yml"]["type"], "infra")
            self.assertIn("ansible", records["roles/web/defaults/main.yml"]["domains"])
            self.assertEqual(records["infra/s3/bucket.yaml"]["type"], "infra")
            self.assertIn("data_storage", records["infra/s3/bucket.yaml"]["domains"])

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

    def test_custom_exclude_extends_default_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print('hi')", encoding="utf-8")
            (root / "mkdocs.yml").write_text("site_name: demo\n", encoding="utf-8")
            (root / "debug.log").write_text("noise\n", encoding="utf-8")

            result = scan_source(str(root), exclude={"*.log"}, workers=1)
            paths = {f["path"] for f in result.files}

            self.assertIn("app.py", paths)
            self.assertNotIn("mkdocs.yml", paths)
            self.assertNotIn("debug.log", paths)
            self.assertTrue(path_in_scan_scope(root, "app.py", exclude={"*.log"}))
            self.assertFalse(path_in_scan_scope(root, "mkdocs.yml", exclude={"*.log"}))
            self.assertFalse(path_in_scan_scope(root, "debug.log", exclude={"*.log"}))

    def test_url_scan_cleans_tempdir_when_scan_fails(self):
        tmp_root = Path(tempfile.mkdtemp())
        (tmp_root / "app.py").write_text("print('hi')", encoding="utf-8")

        with patch("ai_docs.scanner._clone_repo", return_value=(tmp_root, "repo")), \
             patch("ai_docs.scanner._scan_directory", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                scan_source("https://example.com/repo.git", workers=1)

        self.assertFalse(tmp_root.exists())

    def test_build_scan_scope_reuses_loaded_ignore_specs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

            with patch("ai_docs.scanner._load_ignore_specs", wraps=scanner_module._load_ignore_specs) as load_ignore:
                scope = build_scan_scope(root)
                self.assertTrue(scope.includes("app.py"))
                self.assertFalse(scope.includes("ignored.py"))

            load_ignore.assert_called_once_with(root)


if __name__ == "__main__":
    unittest.main()
