"""CLI subprocess tests for the gates and diff subcommands."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "trees" / "router_like"


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "cli.py", *argv], cwd=ROOT, capture_output=True, text=True
    )


def copied_tree(dest: Path) -> Path:
    tree = dest / "tree"
    shutil.copytree(FIXTURE, tree)
    return tree


class CliTests(unittest.TestCase):
    def test_gates_passes_clean_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            result = run_cli("gates", str(copied_tree(dest)))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("router-plugin", result.stdout)

    def test_gates_flags_broken_link_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = copied_tree(Path(tmp))
            skill_md = next(tree.glob("skills/*/SKILL.md"))
            with open(skill_md, "a", encoding="utf-8") as fh:
                fh.write("\n[x](missing.md)\n")
            result = run_cli("gates", str(tree))
            self.assertEqual(result.returncode, 1)
            self.assertIn("broken-link", result.stdout)

    def test_diff_of_two_saved_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            out_a, out_b = dest / "a", dest / "b"
            clean = copied_tree(dest / "clean")
            dirty = copied_tree(dest / "dirty")
            with open(next(dirty.glob("skills/*/SKILL.md")), "a", encoding="utf-8") as fh:
                fh.write("\n[x](missing.md)\n")
            first = run_cli("gates", str(clean), "--out", str(out_a))
            second = run_cli("gates", str(dirty), "--out", str(out_b))
            self.assertEqual(first.returncode, 0, first.stderr)
            old = out_a / sorted(p.name for p in out_a.glob("*.json"))[0]
            new = out_b / sorted(p.name for p in out_b.glob("*.json"))[0]
            result = run_cli("diff", str(old), str(new))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("changed", payload)


if __name__ == "__main__":
    unittest.main()
