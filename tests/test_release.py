import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import unittest

from release import bumped, bump_level


class BumpLevelTests(unittest.TestCase):
    def test_breaking_change_is_major(self):
        self.assertEqual("major", bump_level(["fix: thing", "feat!: new api", "docs: notes"]))
        self.assertEqual("major", bump_level(["add cache", "contains BREAKING CHANGE marker"]))

    def test_feat_is_minor(self):
        self.assertEqual("minor", bump_level(["feat: add op"]))
        self.assertEqual("minor", bump_level(["fix: thing", "chore: [minor] nudge"]))

    def test_default_is_patch(self):
        self.assertEqual("patch", bump_level(["fix: thing"]))
        self.assertEqual("patch", bump_level(["docs: notes", "chore(release): v0.2.0"]))

    def test_skip_marker_does_not_poison_range(self):
        self.assertEqual("patch", bump_level(["docs: notes [skip-release]", "fix: real change"]))


class BumpedTests(unittest.TestCase):
    def test_levels(self):
        self.assertEqual("1.0.0", bumped("0.2.9", "major"))
        self.assertEqual("0.3.0", bumped("0.2.9", "minor"))
        self.assertEqual("0.2.10", bumped("0.2.9", "patch"))


if __name__ == "__main__":
    unittest.main()
