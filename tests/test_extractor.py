"""Tests for engines.extractor behavioral extraction."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.extractor import extract
from engines.profiler import infer_profile
from engines.reader import read_tree

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trees"


class ExtractorTests(unittest.TestCase):
    def test_router_like_yields_grammar_contract(self):
        root = FIXTURES / "router_like"
        model = read_tree(root)
        profile = infer_profile(model)
        result = extract(model, profile)
        self.assertEqual(result["source"], "grammar")
        contract = result["contract"]
        self.assertIsNotNone(contract)
        self.assertEqual(len(contract.routes), 2)
        self.assertTrue(result["fixtures"])
        for fixture in result["fixtures"]:
            got = contract.classify(fixture["request"])
            self.assertEqual(got["route"], fixture["route"], fixture["id"])
            self.assertEqual(got["mutation"], fixture["mutation"], fixture["id"])
        ids = [fixture["id"] for fixture in result["fixtures"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_bare_skill_has_no_grammar(self):
        root = FIXTURES / "bare_skill"
        model = read_tree(root)
        profile = infer_profile(model)
        result = extract(model, profile)
        self.assertEqual(result["source"], "description")
        self.assertIsNone(result["contract"])
        self.assertEqual(result["fixtures"], [])

    def test_dirty_tree_still_extracts_grammar(self):
        root = FIXTURES / "dirty"
        model = read_tree(root)
        profile = infer_profile(model)
        result = extract(model, profile)
        self.assertEqual(result["source"], "grammar")
        self.assertIsNotNone(result["contract"])
        for fixture in result["fixtures"]:
            got = result["contract"].classify(fixture["request"])
            self.assertEqual(got["route"], fixture["route"], fixture["id"])
            self.assertEqual(got["mutation"], fixture["mutation"], fixture["id"])


if __name__ == "__main__":
    unittest.main()
