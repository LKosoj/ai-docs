import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai_docs.generator_output import write_docs
from ai_docs.generator_sections import build_sections, generate_section
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
            self.assertEqual(module_nav_paths, [(expected_module_path, "src/app.py")])
            self.assertEqual(list(config_pages), [expected_config_path])
            self.assertEqual(config_nav_paths, [(expected_config_path, ".github/workflows/build.yml")])

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

    def test_generated_doc_labels_use_source_paths_and_hrefs_use_generated_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_dir = root / ".ai-docs"
            self._write_cached_sections(docs_dir)
            module_summary = self._write_summary(root, "modules/src/v1.2/mod.py.md", "Module summary.")
            config_summary = self._write_summary(
                root,
                "configs/.github/workflows/build.yml.md",
                "Config summary.",
            )
            file_map = {
                "src/v1.2/mod.py": {
                    "type": "code",
                    "domains": [],
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
                    force_sections={"modules", "configs"},
                    regen_all_threshold=0,
                )
            )

            docs_files, _, _, module_nav_paths, config_nav_paths, *_ = result
            module_path = module_doc_path("src/v1.2/mod.py")
            config_path = config_doc_path(".github/workflows/build.yml")
            self.assertIn(f"- [src/v1.2/mod.py]({module_path[len('modules/'):]})", docs_files["modules/index.md"])
            self.assertIn(
                f"- [.github/workflows/build.yml]({config_path[len('configs/'):]})",
                docs_files["configs/index.md"],
            )
            self.assertNotIn("[src/v1.2/mod__py_", docs_files["modules/index.md"])
            self.assertNotIn("[__dot__github", docs_files["configs/index.md"])

            mkdocs_yaml = build_mkdocs_yaml(
                site_name="demo",
                sections=SECTION_TITLES,
                configs={},
                has_modules=True,
                module_nav_paths=module_nav_paths,
                project_config_nav_paths=config_nav_paths,
            )
            nav_lines = [line.strip() for line in mkdocs_yaml.splitlines()]
            self.assertIn(f"- mod.py: {module_path}", nav_lines)
            self.assertIn(f"- build.yml: {config_path}", nav_lines)
            self.assertFalse(any(line.startswith("- mod__py_") for line in nav_lines))
            self.assertFalse(any(line.startswith("- __dot__") for line in nav_lines))
            self.assertIn(module_path, mkdocs_yaml)
            self.assertIn(config_path, mkdocs_yaml)

    def test_cached_module_and_config_indexes_update_generated_hrefs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_dir = root / ".ai-docs"
            self._write_cached_sections(docs_dir)
            (docs_dir / "modules" / "index.md").write_text(
                "# Модули\n\n"
                "Cached intro.\n\n"
                "## Список модулей\n\n"
                "- [src/app.py](src/app__py.md)\n",
                encoding="utf-8",
            )
            (docs_dir / "configs" / "index.md").write_text(
                "# Конфигурация проекта\n\n"
                "## Файлы конфигурации\n\n"
                "- [.github/workflows/build.yml](files/__dot__github/workflows/build__yml.md)\n",
                encoding="utf-8",
            )
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
                    "module_summary_path": str(module_summary),
                },
                ".github/workflows/build.yml": {
                    "type": "config",
                    "domains": [],
                    "config_summary_path": str(config_summary),
                },
            }

            docs_files, *_ = asyncio.run(
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

            module_path = module_doc_path("src/app.py")
            config_path = config_doc_path(".github/workflows/build.yml")
            self.assertIn("Cached intro.", docs_files["modules/index.md"])
            self.assertIn(f"- [src/app.py]({module_path[len('modules/'):]})", docs_files["modules/index.md"])
            self.assertNotIn("src/app__py.md", docs_files["modules/index.md"])
            self.assertIn(
                f"- [.github/workflows/build.yml]({config_path[len('configs/'):]})",
                docs_files["configs/index.md"],
            )
            self.assertNotIn("files/__dot__github/workflows/build__yml.md", docs_files["configs/index.md"])

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

    def test_mkdocs_uses_shared_domain_titles(self):
        mkdocs_yaml = build_mkdocs_yaml(
            site_name="demo",
            sections=SECTION_TITLES,
            configs={
                "service_mesh": "service_mesh.md",
                "data_storage": "data_storage.md",
                "observability": "observability.md",
            },
        )

        self.assertIn("Service Mesh / Ingress", mkdocs_yaml)
        self.assertIn("Data / Storage", mkdocs_yaml)
        self.assertIn("Observability", mkdocs_yaml)
        self.assertNotIn("- service_mesh:", mkdocs_yaml)
        self.assertNotIn("- data_storage:", mkdocs_yaml)

    def test_module_doc_path_preserves_dots_in_directories(self):
        module_path = module_doc_path("src/v1.2/mod.py")
        self.assertTrue(module_path.startswith("modules/src/v1.2/mod__py_"))
        self.assertTrue(module_path.endswith(".md"))

        mkdocs_yaml = build_mkdocs_yaml(
            site_name="demo",
            sections=SECTION_TITLES,
            configs={},
            has_modules=True,
            module_nav_paths=[module_path],
        )

        self.assertIn("/v1.2", mkdocs_yaml)
        self.assertNotIn("v1__2", mkdocs_yaml)

    def test_config_doc_path_sanitizes_hidden_directories_for_mkdocs(self):
        config_path = config_doc_path(".github/workflows/build.yml")
        self.assertTrue(config_path.startswith("configs/files/__dot__github/workflows/build__yml_"))
        self.assertTrue(config_path.endswith(".md"))
        self.assertNotEqual(config_path, config_doc_path("_github/workflows/build.yml"))

    def test_generated_doc_paths_do_not_collide_for_escaped_names(self):
        self.assertNotEqual(
            config_doc_path(".github/workflows/build.yml"),
            config_doc_path("__dot__github/workflows/build.yml"),
        )
        self.assertNotEqual(config_doc_path(".gitlab-ci.yml"), config_doc_path("__gitlab-ci.yml"))
        self.assertNotEqual(config_doc_path("a.b.yml"), config_doc_path("a__b.yml"))

    def test_mkdocs_build_includes_config_from_hidden_source_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_dir = root / ".ai-docs"
            config_path = config_doc_path(".github/workflows/build.yml")
            for rel_path in ("index.md", "overview.md", "changes.md"):
                target = docs_dir / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"# {rel_path}\n", encoding="utf-8")
            config_file = docs_dir / config_path
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text("# GitHub Actions\n", encoding="utf-8")
            asset = docs_dir / "js" / "mermaid.min.js"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_text("", encoding="utf-8")
            (root / "mkdocs.yml").write_text(
                build_mkdocs_yaml(
                    site_name="demo",
                    sections={},
                    configs={},
                    project_config_nav_paths=[config_path],
                    local_site=True,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, "-m", "mkdocs", "build", "-f", "mkdocs.yml"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            built_page = root / "ai_docs_site" / Path(config_path).with_suffix(".html")
            self.assertTrue(built_page.exists())

    def test_dependencies_section_preserves_cached_llm_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_dir = root / ".ai-docs"
            self._write_cached_sections(docs_dir)
            (docs_dir / "dependencies.md").write_text(
                "# Зависимости\n\n"
                "LLM generated dependency overview.\n\n"
                "## Выявленные зависимости\n\n"
                "- old-package\n\n"
                "## Дополнительно\n\n"
                "Keep this note.\n",
                encoding="utf-8",
            )
            file_map = {
                "pyproject.toml": {
                    "type": "config",
                    "domains": [],
                    "content": "[project]\ndependencies = [\"new-package\"]\n",
                }
            }

            docs_files, *_ = asyncio.run(
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

            dependencies = docs_files["dependencies.md"]
            self.assertIn("LLM generated dependency overview.", dependencies)
            self.assertIn("- new-package", dependencies)
            self.assertNotIn("- old-package", dependencies)
            self.assertIn("## Дополнительно\n\nKeep this note.", dependencies)

    def test_dependencies_section_replaces_stale_block_when_dependencies_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_dir = root / ".ai-docs"
            self._write_cached_sections(docs_dir)
            (docs_dir / "dependencies.md").write_text(
                "# Зависимости\n\n"
                "LLM generated dependency overview.\n\n"
                "## Выявленные зависимости\n\n"
                "- old-package\n\n"
                "## Дополнительно\n\n"
                "Keep this note.\n",
                encoding="utf-8",
            )
            file_map = {
                "pyproject.toml": {
                    "type": "config",
                    "domains": [],
                    "content": "[project]\nname = \"demo\"\n",
                }
            }

            docs_files, *_ = asyncio.run(
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

            dependencies = docs_files["dependencies.md"]
            self.assertIn("LLM generated dependency overview.", dependencies)
            self.assertIn("## Выявленные зависимости\n\n- нет", dependencies)
            self.assertNotIn("- old-package", dependencies)
            self.assertIn("## Дополнительно\n\nKeep this note.", dependencies)

    def test_stale_paginated_pages_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            docs_dir = output_root / ".ai-docs"
            stale_module = docs_dir / "modules" / "page-2.md"
            stale_config = docs_dir / "configs" / "page-2.md"
            stale_module.parent.mkdir(parents=True, exist_ok=True)
            stale_config.parent.mkdir(parents=True, exist_ok=True)
            stale_module.write_text("# Old modules page\n", encoding="utf-8")
            stale_config.write_text("# Old configs page\n", encoding="utf-8")
            docs_files = {
                "index.md": "# Index\n",
                "overview.md": "# Overview\n",
                "modules/index.md": "# Modules\n",
                "configs/index.md": "# Configs\n",
            }

            write_docs(output_root, docs_dir, docs_files, {}, {}, {}, has_changes=True)

            index = json.loads((docs_dir / "_index.json").read_text(encoding="utf-8"))
            self.assertFalse(stale_module.exists())
            self.assertFalse(stale_config.exists())
            self.assertNotIn("modules/page-2.md", index["files"])
            self.assertNotIn("configs/page-2.md", index["files"])

    def test_stale_generated_pages_are_removed_without_source_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            docs_dir = output_root / ".ai-docs"
            stale_module_path = module_doc_path("old.py")
            stale_config_path = config_doc_path("old.yml")
            for rel_path in (stale_module_path, stale_config_path):
                stale_file = docs_dir / rel_path
                stale_file.parent.mkdir(parents=True, exist_ok=True)
                stale_file.write_text("# Old\n", encoding="utf-8")
            docs_files = {
                "index.md": "# Index\n",
                "overview.md": "# Overview\n",
                "modules/index.md": "# Modules\n",
                "configs/index.md": "# Configs\n",
            }

            write_docs(output_root, docs_dir, docs_files, {}, {}, {}, has_changes=False)

            index = json.loads((docs_dir / "_index.json").read_text(encoding="utf-8"))
            self.assertFalse((docs_dir / stale_module_path).exists())
            self.assertFalse((docs_dir / stale_config_path).exists())
            self.assertNotIn(stale_module_path, index["files"])
            self.assertNotIn(stale_config_path, index["files"])
            self.assertEqual(index["modules"], [])
            self.assertEqual(index["configs"], [])

    def test_stale_module_and_config_indexes_are_removed_when_no_current_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            docs_dir = output_root / ".ai-docs"
            for rel_path in ("modules/index.md", "configs/index.md"):
                stale_file = docs_dir / rel_path
                stale_file.parent.mkdir(parents=True, exist_ok=True)
                stale_file.write_text("# Old\n", encoding="utf-8")
            docs_files = {
                "index.md": "# Index\n",
                "overview.md": "# Overview\n",
            }

            write_docs(output_root, docs_dir, docs_files, {}, {}, {}, has_changes=False)

            index = json.loads((docs_dir / "_index.json").read_text(encoding="utf-8"))
            self.assertFalse((docs_dir / "modules" / "index.md").exists())
            self.assertFalse((docs_dir / "configs" / "index.md").exists())
            self.assertNotIn("modules/index.md", index["files"])
            self.assertNotIn("configs/index.md", index["files"])
            self.assertFalse(any(section["id"] == "configs" for section in index["sections"]))

    def test_architecture_mermaid_with_parentheses_is_rejected(self):
        class BadMermaidLLM:
            async def chat(self, messages, cache=None):
                return "```mermaid\ngraph TD\nA(Component) --> B\n```"

        with self.assertRaises(RuntimeError):
            asyncio.run(
                generate_section(
                    BadMermaidLLM(),
                    {},
                    "Архитектура",
                    "context",
                    "ru",
                )
            )


if __name__ == "__main__":
    unittest.main()
