"""Tests for engines.profiler profile inference."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.tree import SkillNode, TreeModel
from engines.profiler import infer_profile

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trees"


def make_skill(rel: str) -> SkillNode:
    path = FIXTURES / rel
    return SkillNode(name=path.parent.name, path=path, frontmatter={}, body_lines=0, links=[], references=[])


class ProfilerTests(unittest.TestCase):
    def test_bare_skill_is_single_skill(self):
        root = FIXTURES / "bare_skill"
        model = TreeModel(root=root, manifest=None, skills=[make_skill("bare_skill/SKILL.md")])
        profile = infer_profile(model)
        self.assertEqual(profile.kind, "single-skill")
        self.assertEqual(profile.entry, "bare_skill")
        self.assertEqual(profile.gates, ("links", "leakage", "size", "duplication"))

    def test_skill_collection_has_no_entry(self):
        root = FIXTURES / "skill_collection"
        skills = [make_skill("skill_collection/skills/alpha/SKILL.md"),
                  make_skill("skill_collection/skills/beta/SKILL.md")]
        model = TreeModel(root=root, manifest=None, skills=skills)
        profile = infer_profile(model)
        self.assertEqual(profile.kind, "collection")
        self.assertIsNone(profile.entry)
        self.assertEqual(profile.gates, ("links", "leakage", "size", "duplication"))

    def test_router_like_is_router_plugin(self):
        root = FIXTURES / "router_like"
        manifest = {"name": "router-like"}
        skills = [make_skill("router_like/skills/entry-router/SKILL.md")]
        model = TreeModel(root=root, manifest=manifest, skills=skills)
        profile = infer_profile(model)
        self.assertEqual(profile.kind, "router-plugin")
        self.assertEqual(profile.entry, "entry-router")
        self.assertEqual(
            profile.gates,
            ("manifest", "links", "leakage", "size", "duplication", "routing", "evaluation"),
        )

    def test_grammarless_manifest_skill_is_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = SkillNode(
                name="plain",
                path=Path(tmp) / "plain" / "SKILL.md",
                frontmatter={},
                body_lines=0,
                links=[],
                references=[],
            )
            skill.path.parent.mkdir()
            skill.path.write_text("# Plain\n\nNo routing bullets here.\n", encoding="utf-8")
            model = TreeModel(root=Path(tmp), manifest={"name": "plain"}, skills=[skill])
            profile = infer_profile(model)
        self.assertEqual(profile.kind, "collection")
        self.assertIsNone(profile.entry)
        self.assertIn("manifest", profile.gates)

    def test_manifest_with_no_skills(self):
        model = TreeModel(root=Path("/tmp/nowhere"), manifest={"name": "empty"}, skills=[])
        profile = infer_profile(model)
        self.assertEqual(profile.kind, "collection")
        self.assertIsNone(profile.entry)
        self.assertIn("manifest", profile.gates)


if __name__ == "__main__":
    unittest.main()
