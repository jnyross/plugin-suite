"""Tests for engines.judge advisory reviewer."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.profile import Profile
from contracts.tree import SkillNode, TreeModel
from engines.judge import RUBRICS, RUBRIC_VERSION, check


def make_model(tmp: str) -> TreeModel:
    root = Path(tmp)
    skill_dir = root / "alpha"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: Handles alpha requests.\n---\n\n# Alpha\n\nDo alpha things.\n",
        encoding="utf-8",
    )
    node = SkillNode(
        name="alpha",
        path=skill_dir / "SKILL.md",
        frontmatter={"name": "alpha", "description": "Handles alpha requests."},
        body_lines=3,
        links=[],
        references=[],
    )
    return TreeModel(root=root, manifest={"name": "alpha-pkg", "description": "Alpha package."}, skills=[node])


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.model = make_model(self._tmp.name)
        self.profile = Profile(kind="single-skill", entry="alpha")

    def test_none_adapter_reports_unavailable(self):
        findings = check(self.model, self.profile)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.code, "judge-unavailable")
        self.assertEqual(f.severity, "info")
        self.assertEqual(f.source, "judge")
        self.assertEqual(f.path, str(self.model.root))
        self.assertEqual(f.evidence, "no adapter configured")

    def test_valid_json_array_maps_findings(self):
        payload = (
            '[{"code": "vague-triggers", "severity": "warning", "evidence": "alpha description lacks triggers"},'
            ' {"code": "judge-soft-checks", "severity": "info", "evidence": "verification is vague"}]'
        )
        findings = check(self.model, self.profile, adapter=lambda prompt: payload)
        self.assertEqual([f.code for f in findings], ["judge-vague-triggers", "judge-soft-checks"])
        self.assertTrue(all(f.source == "judge" for f in findings))
        self.assertEqual([f.severity for f in findings], ["warning", "info"])

    def test_prose_wrapped_json_still_parsed(self):
        response = 'Here are my notes:\n[{"code": "split-alpha", "severity": "warning", "evidence": "alpha does too much"}]\nHope that helps!'
        findings = check(self.model, self.profile, adapter=lambda prompt: response)
        self.assertEqual(findings[0].path, "alpha/SKILL.md")

    def test_garbage_response_yields_unparsable(self):
        findings = check(self.model, self.profile, adapter=lambda prompt: "I cannot comply.")
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.code, "judge-unparsable")
        self.assertEqual(f.severity, "info")
        self.assertEqual(f.source, "judge")

    def test_over_long_array_capped_at_twelve(self):
        items = ",".join(f'{{"code": "c{i}", "severity": "info", "evidence": "e{i}"}}' for i in range(20))
        findings = check(self.model, self.profile, adapter=lambda prompt: f"[{items}]")
        self.assertEqual(len(findings), 12)

    def test_severity_coerced_to_info(self):
        payload = '[{"code": "odd", "severity": "critical", "evidence": "bad severity"}]'
        findings = check(self.model, self.profile, adapter=lambda prompt: payload)
        self.assertEqual(findings[0].severity, "info")

    def test_path_maps_to_named_skill_else_root(self):
        payload = (
            '[{"code": "a", "severity": "info", "evidence": "problem in alpha"},'
            ' {"code": "b", "severity": "info", "evidence": "package-wide concern"}]'
        )
        findings = check(self.model, self.profile, adapter=lambda prompt: payload)
        self.assertEqual(findings[0].path, "alpha/SKILL.md")
        self.assertEqual(findings[1].path, str(self.model.root))

    def test_prompt_contains_rubrics_and_material(self):
        seen = {}
        def adapter(prompt: str) -> str:
            seen["prompt"] = prompt
            return "[]"
        check(self.model, self.profile, adapter=adapter)
        prompt = seen["prompt"]
        for rid in RUBRICS:
            self.assertIn(rid, prompt)
        self.assertIn(RUBRIC_VERSION, prompt)
        self.assertIn("alpha", prompt)
        self.assertIn("Handles alpha requests.", prompt)
        self.assertIn("Alpha package.", prompt)


if __name__ == "__main__":
    unittest.main()
