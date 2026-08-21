"""Tests for ops.promote_to_plugin, ops.add_playbook, and ops.dedup_guidance."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.routing_contract import derive_contract
from engines.snapshot import collect
from ops import add_playbook, dedup_guidance, promote_to_plugin

ROOT = Path(__file__).resolve().parents[1]
TREES = ROOT / "tests" / "fixtures" / "trees"
SHARED_LINE = "- Always verify the signed artifact digest before promoting a release candidate."


def copy_tree(name: str) -> Path:
    tmp = Path(tempfile.mkdtemp())
    dest = tmp / name
    shutil.copytree(TREES / name, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def dup_proposals(dest: Path) -> int:
    _, _, findings, _ = collect(dest)
    return sum(1 for finding in findings if finding.code == "duplicate-guidance")


class PromoteToPluginTest(unittest.TestCase):
    def test_promote_writes_manifest_from_first_skill(self):
        dest = copy_tree("skill_collection")
        promote_to_plugin.preconditions(dest, {})
        self.assertEqual({}, promote_to_plugin.predict(dest, {}))
        promote_to_plugin.apply(dest, {})
        manifest = json.loads((dest / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", manifest["$schema"])
        self.assertEqual("skill-collection", manifest["name"])
        self.assertEqual("0.1.0", manifest["version"])
        self.assertEqual("Gathers research notes and open questions.", manifest["description"])
        self.assertEqual("MIT", manifest["license"])

    def test_promote_preconditions_reject_existing_manifest_and_bare_dir(self):
        dest = copy_tree("skill_collection")
        with self.assertRaises(ValueError):
            promote_to_plugin.preconditions(copy_tree("router_like"), {})
        promote_to_plugin.apply(dest, {})
        with self.assertRaises(ValueError):
            promote_to_plugin.preconditions(dest, {})


class AddPlaybookTest(unittest.TestCase):
    def test_add_playbook_routes_and_self_checking_fixtures(self):
        dest = copy_tree("router_like")
        args = {"vocab": ["release", "deploy"], "stem": "release"}
        add_playbook.preconditions(dest, args)
        predicted = add_playbook.predict(dest, args)
        self.assertEqual({"changed": {"routes": 3, "fixtures": 7}}, predicted)

        add_playbook.apply(dest, args)
        skill_md = dest / "skills" / "entry-router" / "SKILL.md"
        lines = skill_md.read_text(encoding="utf-8").splitlines()
        change_idx = next(idx for idx, line in enumerate(lines) if "Select **Change**" in line)
        self.assertIn("Select **Release** for release, or deploy.", lines[change_idx + 1])
        self.assertIn("Read [release.md](references/release.md).", lines[change_idx + 1])

        stub = dest / "skills" / "entry-router" / "references" / "release.md"
        self.assertTrue(stub.is_file())
        self.assertIn("# Release Playbook", stub.read_text(encoding="utf-8"))
        self.assertIn("release, deploy", stub.read_text(encoding="utf-8"))

        cases = json.loads((dest / "tests" / "fixtures" / "router_cases.json").read_text(encoding="utf-8"))
        contract = derive_contract(skill_md)
        self.assertEqual(3, len(contract.routes))
        for case in cases:
            got = contract.classify(case["request"])
            self.assertEqual(case["route"], got["route"], case["id"])
            self.assertEqual(case["mutation"], got["mutation"], case["id"])
        readonly = next(case for case in cases if case["id"] == "release-readonly")
        self.assertEqual(("investigation", "none"), (readonly["route"], readonly["mutation"]))

        # predict matches recomputed post-apply reality
        self.assertEqual(
            predicted["changed"]["routes"],
            sum(1 for line in lines if "- Select **" in line),
        )
        self.assertEqual(predicted["changed"]["fixtures"], len(cases))

        self.assertEqual(0, dup_proposals(dest))  # stub text must not duplicate existing playbooks

    def test_add_playbook_preconditions_reject_bad_args(self):
        fresh = copy_tree("router_like")
        with self.assertRaises(ValueError):
            add_playbook.preconditions(fresh, {"vocab": ["Bad Token"], "stem": "x"})
        dest = copy_tree("router_like")
        add_playbook.apply(dest, {"vocab": ["release", "deploy"], "stem": "release"})
        with self.assertRaises(ValueError):
            add_playbook.preconditions(dest, {"vocab": ["hotfix"], "stem": "release"})


class DedupGuidanceTest(unittest.TestCase):
    def test_dedup_removes_matching_lines_from_duplicates_only(self):
        dest = copy_tree("dirty")
        canonical_rel = "skills/entry-router/references/change.md"
        duplicate_rel = "skills/entry-router/references/extra.md"
        baseline = dup_proposals(dest)
        canonical = dest / canonical_rel
        duplicate = dest / duplicate_rel
        canonical.write_text(canonical.read_text(encoding="utf-8") + SHARED_LINE + "\n", encoding="utf-8")
        duplicate.write_text(duplicate.read_text(encoding="utf-8") + SHARED_LINE + "\n", encoding="utf-8")
        planted = dup_proposals(dest)
        self.assertEqual(baseline + 1, planted)  # planted line is exactly one new proposal

        args = {"canonical": canonical_rel, "duplicates": [duplicate_rel], "line_substr": "artifact digest"}
        dedup_guidance.preconditions(dest, args)
        predicted = dedup_guidance.predict(dest, args)
        self.assertEqual({"severity": {"proposal": planted - 1}}, predicted)

        dedup_guidance.apply(dest, args)
        lowered_duplicate = duplicate.read_text(encoding="utf-8").lower()
        self.assertNotIn("artifact digest", lowered_duplicate)
        self.assertIn("Always verify the signed artifact digest", canonical.read_text(encoding="utf-8"))
        self.assertEqual(planted - 1, dup_proposals(dest))
        self.assertEqual(predicted["severity"]["proposal"], dup_proposals(dest))


if __name__ == "__main__":
    unittest.main()
