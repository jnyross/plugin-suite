"""Tests for the transformer: plan building, gated apply, and whole-tree rollback."""

import hashlib
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines import transformer
from engines.snapshot import collect
from engines.transformer import apply, approve, build_plan, load_op, verify_predicted

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "trees" / "router_like"
CANONICAL = "skills/entry-router/references/investigation.md"
DUPLICATE = "skills/entry-router/references/change.md"
DUP_LINE = (
    "- Always verify the rendered migration output against the recorded golden "
    "snapshot before publishing."
)
PLAYBOOK_ARGS = {"vocab": ["release"], "stem": "release"}
SPLIT_ARGS = {"skill": "entry-router", "new_name": "entry-router-archive", "split_at_line": 300}
DEDUP_ARGS = {"canonical": CANONICAL, "duplicates": [DUPLICATE], "line_substr": "golden snapshot"}
SKIP = {".git", "__pycache__", ".suite", "reports", "decisions"}


def tree_with_duplicate() -> Path:
    tmp = Path(tempfile.mkdtemp())
    dest = tmp / "router_like"
    shutil.copytree(FIXTURE, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    for rel in (CANONICAL, DUPLICATE):
        path = dest / rel
        path.write_text(path.read_text(encoding="utf-8") + "\n" + DUP_LINE + "\n", encoding="utf-8")
    return dest


def tree_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_dir() or set(path.relative_to(root).parts) & SKIP:
            continue
        rel = path.relative_to(root).as_posix()
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def padded_split_tree() -> Path:
    """router_like copy with duplicated guidance and a 600-line entry-router SKILL.md."""
    dest = tree_with_duplicate()
    skill_md = dest / "skills" / "entry-router" / "SKILL.md"
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    pad = [
        f"{n}. Padding guidance line {n} documents a distinct operational concern."
        for n in range(600 - len(lines))
    ]
    skill_md.write_text("\n".join(lines + pad) + "\n", encoding="utf-8")
    return dest


class TransformerTest(unittest.TestCase):
    def test_load_op_resolves_registry_and_rejects_unknown(self):
        self.assertEqual("dedup_guidance", load_op("dedup_guidance").NAME)
        with self.assertRaises(ValueError):
            load_op("no_such_op")

    def test_build_plan_merges_predictions_into_draft(self):
        dest = tree_with_duplicate()
        _, _, findings, _ = collect(dest)
        self.assertEqual(1, sum(1 for f in findings if f.severity == "proposal"))
        plan = build_plan(dest, [("dedup_guidance", DEDUP_ARGS)], rationale="collapse duplicate")
        self.assertEqual("draft", plan.status)
        self.assertRegex(plan.id, re.fullmatch(r"plan-[0-9a-f]{8}", plan.id).re.pattern)
        self.assertEqual(
            {"severity": {"proposal": {"old": None, "new": 0}}}, plan.predicted_delta
        )

    def test_build_plan_later_ops_overwrite_changed_and_sum_severity(self):
        dest = tree_with_duplicate()
        fake_alpha = SimpleNamespace(
            preconditions=lambda t, a: None,
            predict=lambda t, a: {"changed": {"fixtures": {"new": 9}}, "severity": {"info": 2}},
        )
        fake_beta = SimpleNamespace(
            preconditions=lambda t, a: None,
            predict=lambda t, a: {"changed": {"fixtures": {"new": 11}}, "severity": {"info": 3}},
        )
        with mock.patch.dict(sys.modules, {"ops.fake_alpha": fake_alpha, "ops.fake_beta": fake_beta}):
            with mock.patch.object(transformer, "OPS", transformer.OPS + ("fake_alpha", "fake_beta")):
                plan = build_plan(dest, [("fake_alpha", {}), ("fake_beta", {})])
        self.assertEqual(
            {
                "changed": {"fixtures": {"old": None, "new": 11}},
                "severity": {"info": {"old": None, "new": 5}},
            },
            plan.predicted_delta,
        )

    def test_apply_requires_approval(self):
        dest = tree_with_duplicate()
        plan = build_plan(dest, [("dedup_guidance", DEDUP_ARGS)])
        with self.assertRaises(ValueError):
            apply(plan)

    def test_verify_predicted_reports_only_real_mismatches(self):
        actual = {
            "changed": {"fixtures": {"old": 3, "new": 7}},
            "severity": {"proposal": {"old": 1, "new": 0}},
        }
        self.assertEqual([], verify_predicted(actual, actual))
        predicted = {
            "changed": {"fixtures": {"old": 3, "new": 5}},
            "severity": {"proposal": {"new": 2}, "info": {"new": 1}},
        }
        mismatches = verify_predicted(predicted, actual)
        self.assertEqual(3, len(mismatches))

    def test_apply_happy_path_writes_decision_and_keeps_gates_clean(self):
        dest = tree_with_duplicate()
        _, _, findings, _ = collect(dest)
        self.assertEqual([], [f for f in findings if f.severity == "error"])
        plan = build_plan(
            dest,
            [("dedup_guidance", DEDUP_ARGS), ("add_playbook", PLAYBOOK_ARGS)],
            rationale="collapse duplicate and grow the router",
        )
        approve(plan)
        result = apply(plan)
        self.assertEqual("applied", result["status"])
        self.assertEqual("applied", plan.status)
        decision = Path(result["decision"])
        self.assertTrue(decision.is_file())
        self.assertEqual(str(decision), plan.decision_ref)
        text = decision.read_text(encoding="utf-8")
        self.assertIn(plan.id, text)
        self.assertIn("outcome: applied", text)
        self.assertIn("grow the router", text)
        self.assertEqual(
            {
                "changed": {
                    "routes": {"old": None, "new": 3},
                    "fixtures": {"old": None, "new": 7},
                },
                "severity": {"proposal": {"old": None, "new": 0}},
            },
            plan.predicted_delta,
        )
        self.assertEqual([], verify_predicted(plan.predicted_delta, result["actual"]))


    def test_failed_apply_rolls_back_tree_byte_identical(self):
        dest = tree_with_duplicate()
        plan = build_plan(dest, [("dedup_guidance", DEDUP_ARGS)], rationale="doomed run")
        (dest / DUPLICATE).unlink()
        approve(plan)
        before = tree_hashes(dest)
        result = apply(plan)
        self.assertEqual("rolled_back", result["status"])
        self.assertEqual(0, result["at_op"])
        self.assertIn("dedup_guidance", result["reason"])
        self.assertEqual("rolled_back", plan.status)
        self.assertIsNone(plan.decision_ref)
        self.assertEqual(before, tree_hashes(dest))
        self.assertFalse((dest / "decisions").exists())

    def test_partial_mutation_is_fully_rolled_back(self):
        dest = tree_with_duplicate()
        boom = SimpleNamespace(
            preconditions=lambda t, a: None,
            predict=lambda t, a: {},
            apply=lambda t, a: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        with mock.patch.dict(sys.modules, {"ops.fake_boom": boom}):
            with mock.patch.object(transformer, "OPS", transformer.OPS + ("fake_boom",)):
                plan = build_plan(
                    dest, [("add_playbook", PLAYBOOK_ARGS), ("fake_boom", {})], rationale="two-step"
                )
                approve(plan)
                before = tree_hashes(dest)
                result = apply(plan)
        self.assertEqual("rolled_back", result["status"])
        self.assertEqual(1, result["at_op"])
        self.assertIn("boom", result["reason"])
        self.assertEqual(before, tree_hashes(dest))
        self.assertFalse((dest / "decisions").exists())



    def test_merge_dict_shape_and_int_shape_op_predictions(self):
        dest = padded_split_tree()
        plan = build_plan(
            dest,
            [("dedup_guidance", DEDUP_ARGS), ("split_skill", SPLIT_ARGS)],
            rationale="shrink oversized skill",
        )
        self.assertEqual(
            {
                "changed": {"skills": {"old": 1, "new": 2}},
                "severity": {
                    "proposal": {"old": None, "new": 0},
                    "warning": {"old": 0, "new": 1},
                },
            },
            plan.predicted_delta,
        )
        approve(plan)
        result = apply(plan)
        self.assertEqual("applied", result["status"])
        self.assertEqual([], verify_predicted(plan.predicted_delta, result["actual"]))
        self.assertTrue((dest / "skills" / "entry-router-archive" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
