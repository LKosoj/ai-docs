import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from ai_docs.generator_output import write_docs
from ai_docs.generator_sections import build_sections
from ai_docs.generator_shared import (
    SECTION_TITLES,
    config_doc_path,
    module_doc_path,
)
from ai_docs.mkdocs import build_mkdocs_yaml


class FakeLLM:
    model = "gpt-4o-mini"

    async def chat(self, messages, cache=None):
        return "generated content"


class GeneratedDocsTests(unittest.TestCase):
    def _write_summary(self, root: Path, rel_path: str, content: str = "Summary.") -> Path:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _write_cached_sections(self, docs_dir: Path) -> None:
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "overview.md").write_text("# Overview\n\nCached overview\n", encoding="utf-8")
        (docs_dir / "index.md").write_text("# Index\n\nCached index\n", encoding="utf-8")
        for key in SECTION_TITLES:
            (docs_dir / f"{key}.md").write_text(f"# {key}\n\nCached section\n", encoding="utf-8")
        (docs_dir / "modules").mkdir()
        (docs_dir / "modules" / "index.md").write_text("# Modules\n", encoding="utf-8")
        (docs_dir / "configs").mkdir()
        (docs_dir / "configs" / "index.md").write_text("# Configs\n", encoding="utf-8")

    def test_build_sections_uses_generated_doc_helpers_for_pages_and_nav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_dir = root / ".ai-docs"
            self._write_cached_sections(docs_dir)
            file_summary = self._write_summary(root, "summaries/src/app.py.md", "File summary.")
            module_summary = self._write_summary(root, "modules/src/app.py.md", "Module summary.")
            config_summary = self._write_summary(
                root,
                "configs/.github/workflows/build.yml.md",
                "Config summary.",
            )
            file_map = {
                "src/app.py": {
                    "type": "code",
                    "domains": [],
                    "summary_path": str(file_summary),
                    "module_summary_path": str(module_summary),
                },
                ".github/workflows/build.yml": {
                    "type": "config",
                    "domains": [],
                    "config_summary_path": str(config_summary),
                },
            }

            result = asyncio.run(
                build_sections(
                    file_map,
                    {},
                    {},
                    {},
                    docs_dir,
                    FakeLLM(),
                    {},
                    "ru",
                    threads=1,
                    input_budget=2000,
                    regen_all_threshold=0,
                )
            )

            _, module_pages, config_pages, module_nav_paths, config_nav_paths, *_ = result
            expected_module_path = module_doc_path("src/app.py")
            expected_config_path = config_doc_path(".github/workflows/build.yml")
            self.assertEqual(list(module_pages), [expected_module_path])
            self.assertEqual(module_nav_paths, [expected_module_path])
            self.assertEqual(list(config_pages), [expected_config_path])
            self.assertEqual(config_nav_paths, [expected_config_path])

            mkdocs_yaml = build_mkdocs_yaml(
                site_name="demo",
                sections=SECTION_TITLES,
                configs={},
                has_modules=True,
                module_nav_paths=module_nav_paths,
                project_config_nav_paths=config_nav_paths,
            )
            self.assertIn(expected_module_path, mkdocs_yaml)
            self.assertIn(expected_config_path, mkdocs_yaml)

    def test_index_module_path_matches_written_module_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            docs_dir = output_root / ".ai-docs"
            module_path = module_doc_path("src/app.py")
            summary = self._write_summary(output_root, "module-summary.md", "Module summary.")
            docs_files = {
                "index.md": "# Index\n",
                "overview.md": "# Overview\n",
                "modules/index.md": "# Modules\n",
                module_path: "# src/app\n\nModule summary.\n",
            }
            file_map = {
                "src/app.py": {
                    "type": "code",
                    "module_summary_path": str(summary),
                }
            }

            write_docs(output_root, docs_dir, docs_files, file_map, {module_path: ""}, {}, has_changes=True)

            index = json.loads((docs_dir / "_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["modules"][0]["path"], module_path)
            self.assertTrue((docs_dir / index["modules"][0]["path"]).exists())

    def test_index_is_rebuilt_after_cleanup_removes_orphan(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            docs_dir = output_root / ".ai-docs"
            stale_path = docs_dir / "modules" / "old__py.md"
            stale_path.parent.mkdir(parents=True, exist_ok=True)
            stale_path.write_text("# Old\n", encoding="utf-8")
            module_path = module_doc_path("src/app.py")
            summary = self._write_summary(output_root, "module-summary.md", "Module summary.")
            docs_files = {
                "index.md": "# Index\n",
                "overview.md": "# Overview\n",
                "modules/index.md": "# Modules\n",
                module_path: "# src/app\n\nModule summary.\n",
            }
            file_map = {
                "src/app.py": {
                    "type": "code",
                    "module_summary_path": str(summary),
                }
            }

            write_docs(output_root, docs_dir, docs_files, file_map, {module_path: ""}, {}, has_changes=True)

            index = json.loads((docs_dir / "_index.json").read_text(encoding="utf-8"))
            self.assertFalse(stale_path.exists())
            self.assertNotIn("modules/old__py.md", index["files"])


if __name__ == "__main__":
    unittest.main()
