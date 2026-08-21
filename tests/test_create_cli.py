"""CLI subprocess tests for the create subcommand."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FULL_ANSWERS = [
    "demo-skill",
    "Answers demo questions without editing anything.",
    "Explain how the demo index works",
    "",
    "Refactor the demo code",
    "",
    "A question about the demo corpus",
    "read_only",
    "The answer cites a demo source",
    "",
    "Never edits files",
    "",
]


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "cli.py", *argv], cwd=ROOT, capture_output=True, text=True
    )


def answers_file(tmp: Path, answers: list[str]) -> Path:
    path = tmp / "answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    return path


class CreateCliTests(unittest.TestCase):
    def test_create_scaffolds_green_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            result = run_cli(
                "create", "--answers", str(answers_file(tmp, FULL_ANSWERS)),
                "--state-dir", str(tmp / "state"), "--dest", str(tmp / "dest"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("created:", result.stdout)
            self.assertTrue((tmp / "dest" / "plugin.json").exists())
            self.assertTrue((tmp / "state" / ".suite" / "interview.json").exists())
            gates = run_cli("gates", str(tmp / "dest"))
            self.assertEqual(gates.returncode, 0, gates.stdout + gates.stderr)

    def test_create_into_occupied_dir_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dest = tmp / "dest"
            dest.mkdir()
            (dest / "occupied.txt").write_text("keep out", encoding="utf-8")
            result = run_cli(
                "create", "--answers", str(answers_file(tmp, FULL_ANSWERS)),
                "--state-dir", str(tmp / "state"), "--dest", str(dest),
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("not empty", result.stderr)

    def test_create_resumes_from_saved_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            state = tmp / "state"
            first = run_cli(
                "create", "--answers", str(answers_file(tmp, FULL_ANSWERS[:2])),
                "--state-dir", str(state), "--dest", str(tmp / "dest"),
            )
            self.assertEqual(first.returncode, 1)
            self.assertIn("interview incomplete", first.stderr)
            self.assertTrue((state / ".suite" / "interview.json").exists())
            second = run_cli(
                "create", "--answers", str(answers_file(tmp, FULL_ANSWERS[2:])),
                "--state-dir", str(state), "--dest", str(tmp / "dest"),
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue((tmp / "dest" / "plugin.json").exists())
            gates = run_cli("gates", str(tmp / "dest"))
            self.assertEqual(gates.returncode, 0, gates.stdout + gates.stderr)

    def test_create_rejects_non_array_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bad = tmp / "answers.json"
            bad.write_text('{"not": "an array"}', encoding="utf-8")
            result = run_cli(
                "create", "--answers", str(bad),
                "--state-dir", str(tmp / "state"), "--dest", str(tmp / "dest"),
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("JSON array of strings", result.stderr)


if __name__ == "__main__":
    unittest.main()
