"""Profile inference from a TreeModel via the routing decision table."""

import re

from contracts.profile import Profile
from contracts.tree import TreeModel

ROUTE_BULLET = re.compile(r"^\s*-\s*Select\s+\*\*([A-Za-z][A-Za-z ]*)\*\*\s+for\s+([^.]+)\.(.*)$")

_BASE_GATES = ("links", "leakage", "size", "duplication")
_MANIFEST_GATES = ("manifest",) + _BASE_GATES


def _has_route_bullet(node) -> bool:
    text = node.path.read_text(encoding="utf-8") if node.path.is_file() else ""
    return any(ROUTE_BULLET.match(line) for line in text.splitlines())


def infer_profile(model: TreeModel) -> Profile:
    """Infer profile kind, entry skill, and gate set from the tree model."""
    if model.manifest is None:
        if len(model.skills) == 1:
            return Profile("single-skill", entry=model.skills[0].name, gates=_BASE_GATES)
        return Profile("collection", gates=_BASE_GATES)
    candidate = next(
        (skill for skill in model.skills if skill.path.parent.name == model.manifest.get("name")),
        model.skills[0] if model.skills else None,
    )
    if candidate is None:
        return Profile("collection", gates=_MANIFEST_GATES)
    if _has_route_bullet(candidate):
        return Profile(
            "router-plugin",
            entry=candidate.name,
            gates=_MANIFEST_GATES + ("routing", "evaluation"),
        )
    return Profile("collection", gates=_MANIFEST_GATES)
