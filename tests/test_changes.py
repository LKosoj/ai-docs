import unittest

from ai_docs.changes import format_changes_md


class ChangesTests(unittest.TestCase):
    def test_format_changes_md(self):
        added = {"a.txt": {}, "b.txt": {}}
        modified = {"c.txt": {}}
        deleted = {}
        regenerated = ["Архитектура", "Docker"]
        summary = "Кратко о изменениях."
        md = format_changes_md(added, modified, deleted, regenerated, summary)
        self.assertIn("Добавленные файлы", md)
        self.assertIn("a.txt", md)
        self.assertIn("Изменённые файлы", md)
        self.assertIn("c.txt", md)
        self.assertIn("Перегенерированные разделы", md)
        self.assertIn("Архитектура", md)
        self.assertIn("Краткое резюме", md)


if __name__ == "__main__":
    unittest.main()
