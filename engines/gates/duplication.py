"""Duplication gate: flags identical instruction lines shared across reference files."""

import re

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.tree import TreeModel

NAME = "duplication"

MARKER = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")


def _instructions(path) -> set[str]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        stripped = MARKER.sub("", line).strip().lower()
        if len(stripped) >= 45:
            out.add(stripped)
    return out


def run(model: TreeModel, profile: Profile) -> list[Finding]:
    seen: dict[str, list[str]] = {}
    for node in model.skills:
        for ref in node.references:
            rel = ref.relative_to(model.root).as_posix()
            for instruction in _instructions(ref):
                seen.setdefault(instruction, []).append(rel)
    return [
        Finding("duplicate-guidance", "proposal", ", ".join(paths), instruction[:80])
        for instruction, paths in sorted(seen.items())
        if len(set(paths)) >= 2
    ]
