"""Routing gate: checks playbook reachability, fixture coverage, and mutation policy."""

import json
import re

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.tree import TreeModel

NAME = "routing"

ROUTE_REF = re.compile(r"references/([a-z0-9-]+)\.md")
RESERVED = {"playbook-contract"}
POLICY_PHRASES = ("edit the", "modify the", "apply the fix")


def run(model: TreeModel, profile: Profile) -> list[Finding]:
    entry = next((node for node in model.skills if node.name == profile.entry), None)
    if entry is None:
        return []
    findings: list[Finding] = []
    entry_text = entry.path.read_text(encoding="utf-8")
    referenced_routes = set(ROUTE_REF.findall(entry_text)) - RESERVED
    playbooks = {ref.stem for ref in entry.references} - RESERVED
    for stem in sorted(playbooks - referenced_routes):
        findings.append(Finding("unreachable-playbook", "warning", f"skills/{entry.name}/references/{stem}.md",
                                f"playbook {stem!r} is never referenced from {entry.path.name}"))
    for stem in sorted(referenced_routes - playbooks):
        findings.append(Finding("broken-route", "error", f"skills/{entry.name}/references/{stem}.md",
                                f"route references {stem!r} but no such playbook file exists"))
    cases = _fixtures(model)
    if isinstance(cases, list):
        covered = {case.get("route") for case in cases if isinstance(case, dict)}
        for stem in sorted(referenced_routes - covered):
            findings.append(Finding("missing-evaluation", "warning", f"skills/{entry.name}/references/{stem}.md",
                                    f"no fixture exercises route {stem!r}"))
    investigation = entry.path.parent / "references" / "investigation.md"
    if investigation.exists():
        lowered = investigation.read_text(encoding="utf-8").lower()
        hit = next((phrase for phrase in POLICY_PHRASES if phrase in lowered), None)
        if hit:
            findings.append(Finding("mutation-policy-conflict", "error",
                                    investigation.relative_to(model.root).as_posix(),
                                    f"read-only playbook contains change instruction {hit!r}"))
    return findings


def _fixtures(model: TreeModel):
    if model.fixtures_path is None:
        return None
    try:
        return json.loads(model.fixtures_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
