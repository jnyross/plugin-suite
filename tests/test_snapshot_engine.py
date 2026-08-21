"""Tests for the snapshot engine: collect, save/load, and delta."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.snapshot import collect, delta, load, save

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "trees" / "router_like"


def copy_tree() -> Path:
    tmp = Path(tempfile.mkdtemp())
    dest = tmp / "router_like"
    shutil.copytree(FIXTURE, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return dest


class SnapshotEngineTest(unittest.TestCase):
    def test_collect_router_fixture(self):
        model, profile, findings, snapshot = collect(copy_tree())
        self.assertEqual("router-plugin", profile.kind)
        self.assertEqual(3, snapshot.metrics["fixtures"])
        self.assertEqual(2, snapshot.metrics["routes"])
        self.assertEqual([], findings)
        self.assertEqual(1, snapshot.metrics["skills"])

    def test_routes_metric_zero_for_non_router(self):
        bare = ROOT / "tests" / "fixtures" / "trees" / "bare_skill"
        tmp = Path(tempfile.mkdtemp())
        dest = tmp / "bare_skill"
        shutil.copytree(bare, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        *_, snapshot = collect(dest)
        self.assertEqual(0, snapshot.metrics["routes"])

    def test_save_load_round_trip(self):
        *_, snapshot = collect(copy_tree())
        out = Path(tempfile.mkdtemp())
        path = save(snapshot, out)
        self.assertTrue(path.exists())
        restored = load(path)
        self.assertEqual(snapshot.to_dict(), restored.to_dict())
        named = save(snapshot, out, name="custom.json")
        self.assertEqual("custom.json", named.name)

    def test_delta_reports_changed_keys(self):
        *_, old = collect(copy_tree())
        new_tree = copy_tree()
        (new_tree / "tests" / "fixtures" / "router_cases.json").write_text(
            json.dumps([{"id": "x", "request": "r", "route": "investigation", "mutation": "none"}]),
            encoding="utf-8",
        )
        *_, new = collect(new_tree)
        result = delta(old, new)
        self.assertIn("fixtures", result["changed"])
        self.assertEqual(old.metrics["fixtures"], result["changed"]["fixtures"]["old"])
        self.assertEqual(new.metrics["fixtures"], result["changed"]["fixtures"]["new"])

    def test_load_malformed_json_raises(self):
        bad = Path(tempfile.mkdtemp()) / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            load(bad)


if __name__ == "__main__":
    unittest.main()
