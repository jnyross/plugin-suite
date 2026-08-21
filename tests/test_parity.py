"""Integration parity: new pipeline reproduces old script behavior on Plugin-Template."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEMPLATE = Path(os.environ.get("PLUGIN_SUITE_TEMPLATE", Path.home() / "projects" / "Plugin-Template"))
sys.path.insert(0, str(TEMPLATE / "scripts"))

import router_contract as old_rc
import health_audit as old_audit
import validate_plugin as old_validate

from engines.reader import read_tree
from engines.profiler import infer_profile
from engines.gates import run_gates
from engines.routing_contract import derive_contract



def make_copy() -> Path:
    dest = Path(tempfile.mkdtemp(prefix="parity-")) / "template"
    shutil.copytree(
        TEMPLATE,
        dest,
        ignore=shutil.ignore_patterns(".git", ".cache", "reports", "__pycache__"),
    )
    return dest


def new_results(copy: Path):
    model = read_tree(copy)
    profile = infer_profile(model)
    findings = run_gates(model, profile)
    return model, profile, findings


class TestParity(unittest.TestCase):
    def setUp(self):
        if not TEMPLATE.exists():
            self.skipTest("Plugin-Template not available")
        self.tmp = tempfile.TemporaryDirectory(prefix="parity-test-")
        self.addCleanup(self.tmp.cleanup)

    def test_pristine(self):
        copy = make_copy()
        model, profile, findings = new_results(copy)
        self.assertEqual(old_validate.validate(copy), [])
        self.assertEqual(old_audit.audit(copy)["findings"], [])
        self.assertEqual(findings, [])
        self.assertEqual(profile.kind, "router-plugin")
        self.assertEqual(profile.entry, "work-router")

    def test_padded(self):
        copy = make_copy()
        skill_md = copy / "skills" / "work-router" / "SKILL.md"
        with open(skill_md, "a") as fh:
            for i in range(510):
                fh.write("Long instruction %d.%s\n" % (i, "x" * 50))
        _, _, findings = new_results(copy)
        codes = {(f.code, f.severity) for f in findings}
        self.assertIn(("split-required", "proposal"), codes)
        self.assertFalse([f for f in findings if f.severity == "error"])
        audit = old_audit.audit(copy)["findings"]
        self.assertTrue(any(f.get("code") == "split-required" for f in audit))

    def test_deploy_probe(self):
        copy = make_copy()
        (copy / "skills" / "work-router" / "references" / "deploy.md").write_text("# Deploy\n")
        _, _, findings = new_results(copy)
        self.assertIn(("unreachable-playbook", "warning"), {(f.code, f.severity) for f in findings})

    def test_dup_probe(self):
        copy = make_copy()
        line = "\n- Gather concrete runtime evidence before making a decision about the implementation boundary.\n"
        refs = copy / "skills" / "work-router" / "references"
        with open(refs / "investigation.md", "a") as fh:
            fh.write(line)
        with open(refs / "change.md", "a") as fh:
            fh.write(line)
        _, _, findings = new_results(copy)
        self.assertIn(("duplicate-guidance", "proposal"), {(f.code, f.severity) for f in findings})

    def test_classification_parity(self):
        copy = make_copy()
        contract = derive_contract(copy / "skills" / "work-router" / "SKILL.md")
        cases = json.loads((TEMPLATE / "tests" / "fixtures" / "router_cases.json").read_text())
        requests = [c["request"] for c in cases] + [
            "How do I fix the login bug?",
            "Can you fix the login bug?",
            "Review this change for correctness.",
        ]
        for request in requests:
            self.assertEqual(old_rc.classify(request), contract.classify(request), msg=request)


if __name__ == "__main__":
    unittest.main()
