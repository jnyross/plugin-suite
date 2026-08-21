"""Tests for engines.reader tree reading."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.reader import read_tree

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trees"


class ReaderTests(unittest.TestCase):
    def test_bare_skill_single_skill(self):
        model = read_tree(FIXTURES / "bare_skill")
        self.assertIsNone(model.manifest)
        self.assertEqual(len(model.skills), 1)
        skill = model.skills[0]
        self.assertEqual(skill.name, "bare-skill")
        self.assertEqual(skill.frontmatter["description"], "Answers questions about retry logic.")
        self.assertGreater(skill.body_lines, 0)
        self.assertEqual(skill.links, ["references/guide.md"])
        self.assertEqual([path.name for path in skill.references], ["guide.md"])
        self.assertEqual(model.other_files, [])

    def test_router_like_manifest_and_fixtures(self):
        model = read_tree(FIXTURES / "router_like")
        self.assertEqual(model.manifest["name"], "router-like")
        self.assertIsNotNone(model.fixtures_path)
        self.assertEqual(model.fixtures_path.name, "router_cases.json")
        self.assertEqual(len(model.skills), 1)
        skill = model.skills[0]
        self.assertEqual(skill.name, "entry-router")
        self.assertEqual(
            skill.links,
            ["references/investigation.md", "references/change.md"],
        )
        self.assertEqual(len(skill.references), 3)
        self.assertEqual(model.other_files, [])

    def test_skill_collection_cross_link(self):
        model = read_tree(FIXTURES / "skill_collection")
        self.assertEqual([skill.name for skill in model.skills], ["alpha", "beta"])
        self.assertIn("../alpha/SKILL.md", model.skills[1].links)
        self.assertIsNone(model.manifest)
        self.assertIsNone(model.fixtures_path)

    def test_dirty_change_among_references(self):
        model = read_tree(FIXTURES / "dirty")
        self.assertEqual(len(model.skills), 1)
        reference_names = {path.name for path in model.skills[0].references}
        self.assertIn("change.md", reference_names)
        self.assertIn("extra.md", reference_names)

    def test_missing_root_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            with self.assertRaises(FileNotFoundError):
                read_tree(missing)


if __name__ == "__main__":
    unittest.main()
