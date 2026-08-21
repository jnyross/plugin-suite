"""Tests for ops/split_skill.py and ops/extract_principle.py."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ops import extract_principle, split_skill

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "trees" / "router_like"


def copy_tree() -> Path:
    tmp = Path(tempfile.mkdtemp())
    dest = tmp / "router_like"
    shutil.copytree(FIXTURE, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return dest


def pad_skill(root: Path, skill: str, total: int) -> None:
    path = root / "skills" / skill / "SKILL.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    n = 0
    while len(lines) < total:
        n += 1
        lines.append(f"{n}. Padding guidance line {n} documents a distinct operational concern.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def frontmatter(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    meta = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def severity_counts(root: Path) -> dict:
    counts = []
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        counts.append(len(skill_md.read_text(encoding="utf-8").splitlines()))
        refs = skill_md.parent / "references"
        if refs.is_dir():
            counts += [len(p.read_text(encoding="utf-8").splitlines()) for p in sorted(refs.glob("*.md"))]
    return {
        "proposal": sum(1 for n in counts if n > 500),
        "warning": sum(1 for n in counts if 300 < n <= 500),
    }


class SplitSkillTest(unittest.TestCase):
    def setUp(self):
        self.root = copy_tree()
        pad_skill(self.root, "entry-router", 520)
        self.args = {"skill": "entry-router", "new_name": "entry-tail", "split_at_line": 300}

    def test_predict_matches_post_apply_reality(self):
        split_skill.preconditions(self.root, self.args)
        predicted = split_skill.predict(self.root, self.args)
        summary = split_skill.apply(self.root, self.args)
        self.assertIsInstance(summary, str)
        src = self.root / "skills" / "entry-router" / "SKILL.md"
        new = self.root / "skills" / "entry-tail" / "SKILL.md"
        src_lines = src.read_text(encoding="utf-8").splitlines()
        new_lines = new.read_text(encoding="utf-8").splitlines()
        orig = len((FIXTURE / "skills" / "entry-router" / "SKILL.md").read_text(encoding="utf-8").splitlines())
        actual = {
            "changed": {
                "skills": {
                    "old": 1,
                    "new": len(list((self.root / "skills").glob("*/SKILL.md"))),
                }
            },
            "severity": {
                k: {"old": v, "new": severity_counts(self.root)[k]}
                for k, v in {"proposal": 1, "warning": 0}.items()
            },
        }
        actual["severity"] = {
            k: pair for k, pair in actual["severity"].items() if pair["old"] != pair["new"]
        }
        self.assertEqual(actual, predicted)
        self.assertEqual(300, len(src_lines))
        self.assertEqual(227, len(new_lines))
        self.assertTrue(src_lines[-1].startswith(f"{300 - orig}."))
        self.assertEqual("---", new_lines[0])
        self.assertEqual("name: entry-tail", new_lines[1])
        self.assertEqual("description: Extracted from entry-router.", new_lines[2])
        self.assertEqual("# entry-tail", new_lines[5])
        self.assertTrue(new_lines[7].startswith(f"{301 - orig}."))

    def test_split_produces_valid_frontmatter(self):
        split_skill.apply(self.root, self.args)
        for folder in ("entry-router", "entry-tail"):
            meta = frontmatter(self.root / "skills" / folder / "SKILL.md")
            self.assertEqual(folder, meta["name"])
            self.assertTrue(meta["description"])

    def test_preconditions_reject_bad_splits(self):
        with self.assertRaises(ValueError):
            split_skill.preconditions(self.root, {"skill": "nope", "new_name": "x", "split_at_line": 10})
        with self.assertRaises(ValueError):
            split_skill.preconditions(self.root, {**self.args, "split_at_line": 480})
        with self.assertRaises(ValueError):
            split_skill.preconditions(self.root, {**self.args, "new_name": "entry-router"})


class ExtractPrincipleTest(unittest.TestCase):
    def setUp(self):
        self.root = copy_tree()
        self.substr = "answer directly"
        self.args = {"skill": "entry-router", "line_substr": self.substr, "new_name": "principle-fallback"}

    def test_predict_matches_post_apply_reality(self):
        extract_principle.preconditions(self.root, self.args)
        predicted = extract_principle.predict(self.root, self.args)
        self.assertEqual({"changed": {"skills": {"old": 1, "new": 2}}, "severity": {}}, predicted)
        summary = extract_principle.apply(self.root, self.args)
        self.assertIsInstance(summary, str)
        src = self.root / "skills" / "entry-router" / "SKILL.md"
        new = self.root / "skills" / "principle-fallback" / "SKILL.md"
        self.assertNotIn(self.substr, src.read_text(encoding="utf-8"))
        new_lines = new.read_text(encoding="utf-8").splitlines()
        self.assertEqual("name: principle-fallback", new_lines[1])
        self.assertEqual("description: Principle extracted from entry-router.", new_lines[2])
        self.assertTrue(new_lines[5].startswith("- "))
        self.assertIn(self.substr, new_lines[5])
        self.assertEqual(2, len(list((self.root / "skills").glob("*/SKILL.md"))))

    def test_preconditions_reject_bad_extracts(self):
        with self.assertRaises(ValueError):
            extract_principle.preconditions(self.root, {**self.args, "skill": "nope"})
        with self.assertRaises(ValueError):
            extract_principle.preconditions(self.root, {**self.args, "line_substr": "no such line here"})
        src = self.root / "skills" / "entry-router" / "SKILL.md"
        src.write_text(src.read_text(encoding="utf-8") + f"Always {self.substr} when unsure.\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            extract_principle.preconditions(self.root, self.args)
        with self.assertRaises(ValueError):
            extract_principle.preconditions(self.root, {**self.args, "new_name": "entry-router"})


if __name__ == "__main__":
    unittest.main()
