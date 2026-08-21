"""Tests for manifest, links, and leakage gates."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.tree import SkillNode, TreeModel

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(f"engines.gates.{name}", ROOT / "engines" / "gates" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manifest = _load("manifest")
links = _load("links")
leakage = _load("leakage")

PROFILE = Profile(kind="router-plugin", entry="entry-router", gates=("manifest", "links", "leakage"))


def make_tree(tmp: Path, plugin: dict | None = None) -> TreeModel:
    root = tmp / "plugin"
    (root / "skills" / "entry-router" / "references").mkdir(parents=True)
    good = {"$schema": manifest.SCHEMA, "name": "demo", "version": "1.0.0", "description": "d", "license": "MIT"}
    if plugin is not None:
        good.update(plugin)
        for key in [k for k, v in plugin.items() if v is None]:
            del good[key]
    (root / "plugin.json").write_text(json.dumps(good), encoding="utf-8")
    skill_md = root / "skills" / "entry-router" / "SKILL.md"
    skill_md.write_text("---\nname: entry-router\ndescription: Router.\n---\n\nSee [guide](references/guide.md).\n", encoding="utf-8")
    ref = root / "skills" / "entry-router" / "references" / "guide.md"
    ref.write_text("# Guide\n", encoding="utf-8")
    return TreeModel(
        root=root,
        manifest=good,
        skills=[SkillNode("entry-router", skill_md, {"name": "entry-router", "description": "Router."}, 3, [], [ref])],
    )


def codes(findings):
    return {f.code for f in findings}


class ManifestGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def gate(self, plugin=None):
        model = make_tree(Path(self.tmp.name), plugin)
        return manifest.run(model, PROFILE)

    def test_bad_schema(self):
        self.assertIn("manifest-schema", codes(self.gate({"$schema": "https://example.com/x.json"})))

    def test_bad_name(self):
        self.assertIn("manifest-name", codes(self.gate({"name": "Bad_Name"})))

    def test_bad_version(self):
        self.assertIn("manifest-version", codes(self.gate({"version": "1.0"})))

    def test_unknown_field(self):
        found = self.gate({"bogus": 1})
        self.assertIn("manifest-unknown", codes(found))
        self.assertIn("bogus", found[0].evidence)

    def test_skill_frontmatter_and_duplicates(self):
        model = make_tree(Path(self.tmp.name))
        other_dir = model.root / "skills" / "second"
        other_dir.mkdir()
        other_md = other_dir / "SKILL.md"
        other_md.write_text("---\nname: entry-router\n---\nbody\n", encoding="utf-8")
        model.skills.append(SkillNode("entry-router", other_md, {"name": "entry-router"}, 1, [], []))
        found = manifest.run(model, PROFILE)
        self.assertLessEqual({"skill-frontmatter", "skill-duplicate"}, codes(found))
        mismatch = [f for f in found if f.code == "skill-folder-mismatch"]
        self.assertEqual([f.path for f in mismatch], ["skills/second/SKILL.md"])

    def test_clean_manifest_yields_nothing(self):
        self.assertEqual([], self.gate())


class LinksGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_broken_relative_link_detected(self):
        model = make_tree(Path(self.tmp.name))
        model.skills[0].path.write_text(
            "---\nname: entry-router\ndescription: R.\n---\n[missing](references/nope.md)\n", encoding="utf-8"
        )
        found = links.run(model, PROFILE)
        self.assertEqual(1, len(found))
        self.assertEqual(("broken-link", "error", "skills/entry-router/SKILL.md", "references/nope.md"),
                         (found[0].code, found[0].severity, found[0].path, found[0].evidence))

    def test_absolute_url_and_anchor_skipped(self):
        model = make_tree(Path(self.tmp.name))
        model.skills[0].path.write_text(
            "---\nname: entry-router\ndescription: R.\n---\n[a](https://x.example/y) [b](#section)\n", encoding="utf-8"
        )
        self.assertEqual([], links.run(model, PROFILE))

    def test_readme_checked(self):
        model = make_tree(Path(self.tmp.name))
        (model.root / "README.md").write_text("[gone](docs/absent.md)\n", encoding="utf-8")
        found = links.run(model, PROFILE)
        self.assertEqual(["broken-link"], [f.code for f in found])
        self.assertEqual("README.md", found[0].path)

    def test_directory_target_accepted(self):
        model = make_tree(Path(self.tmp.name))
        (model.root / "skills" / "extra").mkdir()
        model.skills[0].path.write_text(
            "---\nname: entry-router\ndescription: R.\n---\n[skills/](../extra/) [gone](nope/)\n", encoding="utf-8"
        )
        found = links.run(model, PROFILE)
        self.assertEqual(1, len(found))
        self.assertEqual("nope/", found[0].evidence)


class LeakageGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_marker_detected(self):
        model = make_tree(Path(self.tmp.name))
        model.skills[0].references[0].write_text("Use a Cursor Task here.\n", encoding="utf-8")
        found = leakage.run(model, PROFILE)
        self.assertEqual(1, len(found))
        self.assertEqual(("client-leakage", "warning"), (found[0].code, found[0].severity))
        self.assertEqual("skills/entry-router/references/guide.md", found[0].path)
        self.assertEqual("Cursor Task", found[0].evidence)

    def test_client_path_error(self):
        model = make_tree(Path(self.tmp.name))
        (model.root / ".claude-plugin").mkdir()
        found = leakage.run(model, PROFILE)
        self.assertEqual([("client-path", "error")], [(f.code, f.severity) for f in found])

    def test_packaging_dir_with_manifest_is_warning(self):
        model = make_tree(Path(self.tmp.name))
        packaging = model.root / ".codex-plugin"
        packaging.mkdir()
        (packaging / "plugin.json").write_text('{"name": "x"}', encoding="utf-8")
        found = leakage.run(model, PROFILE)
        self.assertEqual([("client-path", "warning")], [(f.code, f.severity) for f in found])
        self.assertIn("deliberate client packaging", found[0].evidence)

    def test_packaging_dir_without_manifest_stays_error(self):
        model = make_tree(Path(self.tmp.name))
        (model.root / ".codex-plugin").mkdir()
        found = leakage.run(model, PROFILE)
        self.assertEqual([("client-path", "error")], [(f.code, f.severity) for f in found])

    def test_clean_tree_no_findings(self):
        self.assertEqual([], leakage.run(make_tree(Path(self.tmp.name)), PROFILE))

class FixtureTreeTest(unittest.TestCase):
    def _model(self, root: Path) -> TreeModel:
        manifest_data = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        skills = []
        for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            raw = text.split("---\n", 2)[1]
            meta = {k.strip(): v.strip() for line in raw.splitlines() if ":" in line for k, v in [line.split(":", 1)]}
            refs = sorted((skill_md.parent / "references").glob("*.md"))
            skills.append(SkillNode(meta.get("name", ""), skill_md, meta, len(text.splitlines()), [], refs))
        return TreeModel(root=root, manifest=manifest_data, skills=skills)

    def test_router_like_fixture_clean(self):
        model = self._model(ROOT / "tests" / "fixtures" / "trees" / "router_like")
        findings = manifest.run(model, PROFILE) + links.run(model, PROFILE) + leakage.run(model, PROFILE)
        self.assertEqual([], findings)
        self.assertEqual("manifest", manifest.NAME)
        self.assertEqual("links", links.NAME)
        self.assertEqual("leakage", leakage.NAME)

if __name__ == "__main__":
    unittest.main()
