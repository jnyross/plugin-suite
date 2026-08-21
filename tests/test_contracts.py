import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import (
    DEFAULT_THRESHOLDS,
    Finding,
    OpCall,
    Plan,
    Profile,
    SkillNode,
    Snapshot,
    Spec,
    TreeModel,
    build_snapshot,
    diff,
)


class FindingTests(unittest.TestCase):
    def test_invalid_severity_raises(self):
        with self.assertRaises(ValueError):
            Finding(code="x", severity="fatal", path="p", evidence="e")

    def test_dict_round_trip(self):
        f = Finding(code="large-file", severity="warning", path="a/SKILL.md", evidence="320 lines")
        self.assertEqual(Finding.from_dict(f.to_dict()), f)

    def test_defaults(self):
        f = Finding(code="c", severity="info", path="p", evidence="e")
        self.assertEqual(f.source, "gate")
        self.assertIsNone(f.op_hint)
        d = f.to_dict()
        self.assertEqual(d["source"], "gate")
        self.assertIsNone(d["op_hint"])
        self.assertEqual(Finding.from_dict(d), f)


class ProfileTests(unittest.TestCase):
    def test_invalid_kind_raises(self):
        with self.assertRaises(ValueError):
            Profile(kind="mega-plugin")

    def test_router_plugin_requires_entry(self):
        with self.assertRaises(ValueError):
            Profile(kind="router-plugin")
        p = Profile(kind="router-plugin", entry="work-router")
        self.assertEqual(p.entry, "work-router")

    def test_collection_entry_forbidden(self):
        with self.assertRaises(ValueError):
            Profile(kind="collection", entry="work-router")
        self.assertIsNone(Profile(kind="collection").entry)

    def test_single_skill_allows_entry(self):
        p = Profile(kind="single-skill", entry="work-router")
        self.assertEqual(p.entry, "work-router")
        self.assertIsNone(Profile(kind="single-skill").entry)

    def test_thresholds_default_copy(self):
        p = Profile(kind="single-skill")
        self.assertEqual(p.thresholds, DEFAULT_THRESHOLDS)
        p.thresholds["large_file"] = 1
        self.assertEqual(DEFAULT_THRESHOLDS["large_file"], 300)


class SpecTests(unittest.TestCase):
    def make(self, **overrides):
        base = dict(
            name="add-release-path",
            purpose="Add a release route",
            triggers=["Deploy the service"],
            non_triggers=["Explain deployment"],
            inputs="repo tree",
            mutation_policy="scoped",
            verification=["routes == 3"],
            boundaries=["never touches .git"],
        )
        base.update(overrides)
        return Spec(**base)

    def test_valid_spec_passes(self):
        self.make().validate()

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            self.make(name="").validate()

    def test_bad_name_case_rejected(self):
        for bad in ("AddRelease", "add release", "add_release", "-lead", "trail-"):
            with self.assertRaises(ValueError, msg=bad):
                self.make(name=bad).validate()

    def test_bad_policy_rejected(self):
        with self.assertRaises(ValueError):
            self.make(mutation_policy="yolo").validate()

    def test_round_trip(self):
        s = self.make(open_questions=["which env?"])
        self.assertEqual(Spec.from_dict(s.to_dict()), s)


class PlanTests(unittest.TestCase):
    def make(self, **overrides):
        base = dict(
            id="plan-0a1b2c3d",
            target="/tmp/tree",
            ops=[OpCall(op="add_file", args={"path": "x.md"}, rationale="grow coverage")],
            predicted_delta={"changed": {"skills": {"old": 2, "new": 3}}, "severity": {}},
            rollback={"strategy": "restore", "snapshots": []},
        )
        base.update(overrides)
        return Plan(**base)

    def test_legal_transitions(self):
        p = self.make()
        p.transition("approved")
        self.assertEqual(p.status, "approved")
        p.transition("applied")
        self.assertEqual(p.status, "applied")

    def test_rollback_from_approved(self):
        p = self.make()
        p.transition("approved")
        p.transition("rolled_back")
        self.assertEqual(p.status, "rolled_back")

    def test_illegal_transitions(self):
        p = self.make()
        with self.assertRaises(ValueError):
            p.transition("applied")
        with self.assertRaises(ValueError):
            p.transition("rolled_back")
        p.transition("approved")
        p.transition("applied")
        with self.assertRaises(ValueError):
            p.transition("rolled_back")

    def test_round_trip_nested_ops(self):
        p = self.make(decision_ref="dec-42")
        restored = Plan.from_dict(p.to_dict())
        self.assertEqual(restored, p)
        self.assertIsInstance(restored.ops[0], OpCall)
        self.assertEqual(restored.ops[0], p.ops[0])

    def test_from_dict_defaults(self):
        d = self.make().to_dict()
        del d["status"], d["decision_ref"]
        p = Plan.from_dict(d)
        self.assertEqual(p.status, "draft")
        self.assertIsNone(p.decision_ref)


    def make_model(self, root: Path) -> TreeModel:
        skill_dir = root / "skills" / "work-router"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# router\n" + "line\n" * 12, encoding="utf-8")
        refs = skill_dir / "references"
        refs.mkdir()
        (refs / "investigation.md").write_text("a\n" * 40, encoding="utf-8")
        (refs / "change.md").write_text("b\n" * 5, encoding="utf-8")
        (refs / "ignored.txt").write_text("skip", encoding="utf-8")
        node = SkillNode(
            name="work-router",
            path=skill_dir / "SKILL.md",
            frontmatter={"name": "work-router"},
            body_lines=13,
            links=["references/investigation.md", "references/change.md"],
            references=sorted(refs.glob("*.md")),
        )
        fixtures = root / "tests" / "fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "router_cases.json").write_text(
            '[{"id": "a"}, {"id": "b"}, {"id": "c"}]', encoding="utf-8"
        )
        return TreeModel(
            root=root,
            manifest={"name": "plugin"},
            skills=[node],
            fixtures_path=fixtures / "router_cases.json",
        )

    def test_build_snapshot_metrics(self):
        findings = [
            Finding("large-file", "warning", "a", "e"),
            Finding("large-file", "warning", "b", "e"),
            Finding("split-required", "proposal", "c", "e"),
            Finding("note", "info", "d", "e"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            model = self.make_model(Path(tmp))
            snap = build_snapshot(model, Profile(kind="router-plugin", entry="work-router"),
                                  findings, extra_metrics={"routes": 2})
        self.assertEqual(snap.gates_version, "1")
        self.assertEqual(snap.metrics["skills"], 1)
        self.assertEqual(snap.metrics["references"], 2)
        self.assertEqual(snap.metrics["routes"], 2)
        self.assertEqual(snap.metrics["fixtures"], 3)
        self.assertEqual(
            snap.metrics["findings_by_severity"],
            {"warning": 2, "proposal": 1, "info": 1},
        )
        largest = snap.metrics["largest_files"]
        self.assertEqual(len(largest), 3)
        self.assertEqual(largest[0], ["skills/work-router/references/investigation.md", 40])
        self.assertEqual(largest[1], ["skills/work-router/SKILL.md", 13])
        self.assertEqual(largest[2], ["skills/work-router/references/change.md", 5])
        self.assertTrue(snap.generated_at.endswith("+00:00"))
        self.assertRegex(snap.generated_at, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")

    def test_snapshot_without_fixtures_or_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self.make_model(Path(tmp))
            model.fixtures_path = None
            snap = build_snapshot(model, Profile(kind="single-skill"), [])
        self.assertEqual(snap.metrics["fixtures"], 0)
        self.assertEqual(snap.metrics["routes"], 0)
        self.assertEqual(snap.metrics["findings_by_severity"], {})
        self.assertEqual(snap.profile_kind, "single-skill")

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = build_snapshot(self.make_model(Path(tmp)), Profile(kind="single-skill"), [])
        self.assertEqual(Snapshot.from_dict(snap.to_dict()), snap)

    def test_diff_scalar_and_severity(self):
        old = Snapshot("t", "single-skill", "1", {"skills": 2, "routes": 1,
                                                  "findings_by_severity": {"warning": 1}})
        new = Snapshot("t", "single-skill", "1", {"skills": 3, "routes": 1,
                                                  "findings_by_severity": {"warning": 0, "error": 2}})
        d = diff(old, new)
        self.assertEqual(d["changed"], {"skills": {"old": 2, "new": 3}})
        self.assertEqual(d["severity"], {"warning": {"old": 1, "new": 0},
                                         "error": {"old": 0, "new": 2}})

    def test_diff_missing_keys_tolerated(self):
        old = Snapshot("t", "k", "1", {"skills": 2})
        new = Snapshot("t", "k", "1", {"skills": 2, "routes": 4,
                                       "findings_by_severity": {"error": 1}})
        d = diff(old, new)
        self.assertEqual(d["changed"], {"routes": {"old": None, "new": 4}})
        self.assertEqual(d["severity"], {"error": {"old": 0, "new": 1}})
        empty = diff(Snapshot("t", "k", "1", {}), Snapshot("t", "k", "1", {}))
        self.assertEqual(empty, {"changed": {}, "severity": {}})


if __name__ == "__main__":
    unittest.main()
