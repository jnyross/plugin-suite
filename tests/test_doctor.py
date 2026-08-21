"""Doctor engine and CLI subcommand tests."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from engines import doctor

ROOT = Path(__file__).resolve().parents[1]
ROUTER_LIKE = ROOT / "tests" / "fixtures" / "trees" / "router_like"
BARE_SKILL = ROOT / "tests" / "fixtures" / "trees" / "bare_skill"


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "cli.py", *argv], cwd=ROOT, capture_output=True, text=True
    )


def copied(dest: Path, fixture: Path) -> Path:
    tree = dest / "tree"
    shutil.copytree(fixture, tree)
    return tree


class DoctorEngineTests(unittest.TestCase):
    def test_router_like_diagnoses_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = doctor.diagnose(copied(Path(tmp), ROUTER_LIKE))
        self.assertEqual(report["profile"], {"kind": "router-plugin", "entry": "entry-router"})
        self.assertEqual(report["extraction"]["source"], "grammar")
        self.assertEqual(report["extraction"]["routes"], 2)
        self.assertEqual(report["extraction"]["generated_fixtures"], 5)
        codes = [f.code for f in report["findings"]]
        self.assertNotIn("extracted-fixture-failure", codes)
        gate_errors = [
            f for f in report["findings"] if f.severity == "error" and f.source != "judge"
        ]
        self.assertEqual(gate_errors, [])

    def test_judge_warning_surfaces_without_exit_effect(self):
        def adapter(prompt: str) -> str:
            return json.dumps(
                [{"code": "judge-vague", "severity": "warning", "evidence": "entry-router is vague"}]
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = doctor.diagnose(copied(Path(tmp), ROUTER_LIKE), adapter=adapter)
        judge_findings = [f for f in report["findings"] if f.source == "judge"]
        self.assertEqual([f.code for f in judge_findings], ["judge-vague"])
        self.assertEqual(judge_findings[0].severity, "warning")

    def test_bare_skill_uses_description_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = doctor.diagnose(copied(Path(tmp), BARE_SKILL))
        self.assertEqual(report["profile"]["kind"], "single-skill")
        self.assertEqual(report["extraction"]["source"], "description")
        self.assertEqual(report["extraction"]["generated_fixtures"], 0)
        infos = [f for f in report["findings"] if f.code == "judge-unavailable"]
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].severity, "info")
        self.assertEqual(infos[0].source, "judge")


class DoctorCliTests(unittest.TestCase):
    def test_clean_tree_exits_zero_with_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("doctor", str(copied(Path(tmp), ROUTER_LIKE)))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Recommendations", proc.stdout)

    def test_broken_link_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = copied(Path(tmp), ROUTER_LIKE)
            skill_md = tree / "skills" / "entry-router" / "SKILL.md"
            skill_md.write_text(skill_md.read_text(encoding="utf-8").replace("change.md", "missing.md"), encoding="utf-8")
            proc = run_cli("doctor", str(tree))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("broken-link", proc.stdout)

    def test_json_and_out_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "reports"
            proc = run_cli("doctor", str(copied(Path(tmp), ROUTER_LIKE)), "--json", "--out", str(out_dir))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["extraction"]["source"], "grammar")
            saved = json.loads((out_dir / "doctor-report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["profile"]["kind"], "router-plugin")
            self.assertIsInstance(saved["findings"][0], dict)


if __name__ == "__main__":
    unittest.main()
