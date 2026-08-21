"""Tests for the scaffolder's green-at-birth plugin generation."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.spec import Spec
from engines.scaffolder import scaffold
from engines.snapshot import collect


def _spec(**overrides) -> Spec:
    data = dict(
        name="retry-whisperer",
        purpose="Advises on retry backoff strategies for flaky network calls.",
        triggers=["How do I tune the retry budget for a flaky endpoint?"],
        non_triggers=["Rewriting HTTP client libraries."],
        inputs="A request describing the flaky call pattern.",
        mutation_policy="read_only",
        verification=["Fixtures under tests/fixtures pass evaluation."],
        boundaries=["Never edits client code directly."],
    )
    data.update(overrides)
    return Spec(**data)


class TestScaffolder(unittest.TestCase):
    def test_read_only_spec_is_green_at_birth(self):
        spec = _spec(triggers=[
            "Explain how the retry budget is computed.",
            "How do I tune the retry budget for a flaky endpoint?",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "plugin"
            result = scaffold(spec, dest)
            self.assertEqual(result, dest)
            model, profile, findings, _ = collect(dest)
            errors = [f for f in findings if f.severity == "error"]
            self.assertEqual(errors, [])
            self.assertIn(profile.kind, ("router-plugin", "collection-with-manifest"))
            evals = [f for f in findings if f.code == "evaluation-failure"]
            self.assertEqual(evals, [])

    def test_scoped_spec_routes_fix_trigger_to_change(self):
        spec = _spec(
            name="bug-mender",
            purpose="Repairs reported defects in service code.",
            triggers=["Fix the login timeout bug in the auth module."],
            non_triggers=["Reviews only; no fixes requested."],
            mutation_policy="scoped",
        )
        with tempfile.TemporaryDirectory() as tmp:
            dest = scaffold(spec, Path(tmp) / "plugin")
            cases = __import__("json").loads(
                (dest / "tests" / "fixtures" / "router_cases.json").read_text())
            self.assertEqual(cases[0]["route"], "change")
            self.assertEqual(cases[0]["mutation"], "scoped")
            _, _, findings, _ = collect(dest)
            self.assertEqual([f for f in findings if f.severity == "error"], [])

    def test_non_empty_destination_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "plugin"
            dest.mkdir()
            (dest / "occupied.txt").write_text("x")
            with self.assertRaises(ValueError):
                scaffold(_spec(), dest)

    def test_broad_spec_produces_three_playbooks(self):
        spec = _spec(
            name="platform-mover",
            purpose="Executes approved platform-wide changes.",
            triggers=["Escalate the schema migration to every region."],
            non_triggers=["Single-file fixes."],
            mutation_policy="broad",
        )
        with tempfile.TemporaryDirectory() as tmp:
            dest = scaffold(spec, Path(tmp) / "plugin")
            refs = sorted(p.name for p in (dest / "skills" / "platform-mover" / "references").glob("*.md"))
            self.assertEqual(refs, ["approve.md", "change.md", "investigate.md"])


if __name__ == "__main__":
    unittest.main()
