"""Tests for routing_contract and the routing-family gates."""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.tree import SkillNode, TreeModel
from engines.gates import duplication, evaluation, routing, size

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trees"
FM = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _frontmatter(text: str) -> dict:
    match = FM.match(text)
    data = {}
    if match:
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    return data


CANONICAL_CASES = [
    {"id": "explain-q", "request": "Explain the retry logic.", "route": "investigation", "mutation": "none"},
    {"id": "implement-pos", "request": "Implement pagination.", "route": "change", "mutation": "scoped"},
    {"id": "ambiguous", "request": "The settings feel wrong.", "route": "fallback", "mutation": "none"},
]


def load(tree: str) -> tuple[TreeModel, Profile]:
    """Copy a fixture tree into a private tmpdir (never touching the shared tree)."""
    root = Path(tempfile.mkdtemp(prefix="gates-routing-")) / tree
    shutil.copytree(FIXTURES / tree, root)
    fixtures = root / "tests" / "fixtures" / "router_cases.json"
    if fixtures.exists():
        cases = json.loads(fixtures.read_text(encoding="utf-8"))
        if {c.get("id") for c in cases} != {c["id"] for c in CANONICAL_CASES}:
            fixtures.write_text(json.dumps(CANONICAL_CASES), encoding="utf-8")
    skills = []
    for skill_dir in sorted((root / "skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        match = FM.match(text)
        body = text[match.end():] if match else text
        refs_dir = skill_dir / "references"
        skills.append(SkillNode(
            name=skill_dir.name,
            path=skill_md,
            frontmatter=_frontmatter(text),
            body_lines=len(body.splitlines()),
            links=re.findall(r"\]\(([^)]+)\)", text),
            references=sorted(refs_dir.glob("*.md")) if refs_dir.exists() else [],
        ))
    fixtures = root / "tests" / "fixtures" / "router_cases.json"
    manifest_path = root / "plugin.json"
    return TreeModel(
        root=root,
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None,
        skills=skills,
        fixtures_path=fixtures if fixtures.exists() else None,
    ), Profile("router-plugin", entry="entry-router")



class RoutingContractTest(unittest.TestCase):
    def test_derive_and_classify(self):
        from engines.routing_contract import derive_contract

        contract = derive_contract(FIXTURES / "router_like" / "skills" / "entry-router" / "SKILL.md")
        self.assertEqual([r.stem for r in contract.routes], ["investigation", "change"])
        self.assertEqual(contract.classify("How does the retry logic work?"),
                         {"route": "investigation", "mutation": "none", "reason": "explanatory or advisory question"})
        self.assertEqual(contract.classify("Explain the retry logic."),
                         {"route": "investigation", "mutation": "none", "reason": "read-only inquiry intent"})
        self.assertEqual(contract.classify("Implement pagination."),
                         {"route": "change", "mutation": "scoped", "reason": "explicit change intent"})
        self.assertEqual(contract.classify("The settings feel wrong."),
                         {"route": "fallback", "mutation": "none", "reason": "no proven playbook match"})
        self.assertEqual(contract.classify("Explain it but do not change anything."),
                         {"route": "investigation", "mutation": "none", "reason": "explicit read-only constraint"})

    def test_duplicate_vocab_exits(self):
        from engines.routing_contract import derive_contract

        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "SKILL.md"
            skill.write_text(
                "- Select **A** for fix, or build. Read [a.md](references/a.md).\n"
                "- Select **B** for fix. Read [b.md](references/b.md).\n",
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                derive_contract(skill)

    def test_unparsable_token_exits(self):
        from engines.routing_contract import derive_contract

        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "SKILL.md"
            skill.write_text("- Select **A** for Fix It! Read [a.md](references/a.md).\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                derive_contract(skill)


class GatesTest(unittest.TestCase):
    def test_dirty_tree_flags(self):
        model, profile = load("dirty")
        size_findings = size.run(model, profile)
        self.assertIn(("large-file", "warning"),
                      [(f.code, f.severity) for f in size_findings])
        self.assertNotIn("split-required", [f.code for f in size_findings])
        dup_codes = [(f.code, f.severity) for f in duplication.run(model, profile)]
        self.assertIn(("duplicate-guidance", "proposal"), dup_codes)
        route_codes = {f.code for f in routing.run(model, profile)}
        self.assertIn("unreachable-playbook", route_codes)
        self.assertNotIn("broken-route", route_codes)

    def test_router_like_pristine(self):
        model, profile = load("router_like")
        findings = size.run(model, profile) + duplication.run(model, profile) + routing.run(model, profile)
        self.assertEqual(findings, [])
        eval_findings = evaluation.run(model, profile)
        self.assertEqual(eval_findings, [])

    def test_router_like_evaluation_passes_fixtures(self):
        model, profile = load("router_like")
        cases = json.loads(model.fixtures_path.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 3)
        self.assertEqual(evaluation.run(model, profile), [])

    def test_mutation_policy_conflict(self):
        model, profile = load("router_like")
        investigation = model.root / "skills" / "entry-router" / "references" / "investigation.md"
        original = investigation.read_text(encoding="utf-8")
        investigation.write_text(original + "\nEdit the config before answering.\n", encoding="utf-8")
        try:
            codes = [(f.code, f.severity) for f in routing.run(model, profile)]
        finally:
            investigation.write_text(original, encoding="utf-8")
        self.assertIn(("mutation-policy-conflict", "error"), codes)

    def test_padded_skill_triggers_split_required(self):
        model, profile = load("router_like")
        node = model.skills[0]
        padded = SkillNode(node.name, node.path, node.frontmatter, 501, node.links, node.references)
        big = TreeModel(model.root, model.manifest, [padded], model.fixtures_path, model.other_files)
        codes = [(f.code, f.severity) for f in size.run(big, profile)]
        self.assertIn(("split-required", "proposal"), codes)
        self.assertNotIn("large-file", [c for c, _ in codes])

    def test_missing_evaluation(self):
        model, profile = load("router_like")
        cases = json.loads(model.fixtures_path.read_text(encoding="utf-8"))
        trimmed = [c for c in cases if c["route"] != "investigation"]
        model.fixtures_path.write_text(json.dumps(trimmed), encoding="utf-8")
        codes = {f.code for f in routing.run(model, profile)}
        self.assertIn("missing-evaluation", codes)


if __name__ == "__main__":
    unittest.main()
