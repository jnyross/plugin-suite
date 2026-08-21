"""Evaluation gate: replays router fixtures against the derived routing contract."""

import json
import sys
from pathlib import Path

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.tree import TreeModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engines.routing_contract import derive_contract  # noqa: E402

NAME = "evaluation"


def run(model: TreeModel, profile: Profile) -> list[Finding]:
    if not profile.entry or model.fixtures_path is None:
        return []
    try:
        cases = json.loads(model.fixtures_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if not isinstance(cases, list) or not cases:
        return []
    entry = next((node for node in model.skills if node.name == profile.entry), None)
    if entry is None:
        return []
    try:
        contract = derive_contract(entry.path)
    except SystemExit:
        return []
    findings: list[Finding] = []
    for case in cases:
        case_id = str(case.get("id", "<unnamed>"))
        expected = contract.classify(case.get("request", ""))
        for field in ("route", "mutation"):
            want = case.get(field)
            got = expected[field]
            if want != got:
                findings.append(Finding(
                    "evaluation-failure",
                    "error",
                    case_id,
                    f"{field}: expected {want!r}, contract produced {got!r} ({expected['reason']})",
                ))
    return findings
