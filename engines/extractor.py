"""Behavioral fixture extraction from a plugin tree's routing grammar."""

from contracts.profile import Profile
from contracts.tree import TreeModel
from engines.routing_contract import Contract, derive_contract


def _entry_skill(model: TreeModel, profile: Profile):
    if not profile.entry:
        return None
    return next(
        (
            skill
            for skill in model.skills
            if profile.entry in (skill.name, skill.path.parent.name)
        ),
        None,
    )


def _fixtures_for(contract: Contract) -> list[dict]:
    read_only = contract.routes[0]
    token = sorted(read_only.vocab)[0]
    fixtures = [
        {
            "id": f"{read_only.stem}-inquiry",
            "request": f"How does the {token} work?",
            "route": read_only.stem,
            "mutation": "none",
        }
    ]
    for route in contract.routes[1:]:
        token = sorted(route.vocab)[0]
        fixtures.extend(
            [
                {
                    "id": f"{route.stem}-positive",
                    "request": f"Please {token} the module.",
                    "route": route.stem,
                    "mutation": "scoped",
                },
                {
                    "id": f"{route.stem}-readonly",
                    "request": f"Explain the {route.stem} process but do not change anything.",
                    "route": read_only.stem,
                    "mutation": "none",
                },
                {
                    "id": f"{route.stem}-dual",
                    "request": f"Investigate and {token} the fix.",
                    "route": route.stem,
                    "mutation": "scoped",
                },
                {
                    "id": f"{route.stem}-ambiguous",
                    "request": f"Get the {token} ready.",
                    "route": "fallback",
                    "mutation": "none",
                },
            ]
        )
    return fixtures


def _self_check(contract: Contract, fixtures: list[dict]) -> None:
    for fixture in fixtures:
        got = contract.classify(fixture["request"])
        if got["route"] != fixture["route"] or got["mutation"] != fixture["mutation"]:
            raise ValueError(
                f"generated fixture {fixture['id']!r} drifted: expected "
                f"{fixture['route']}/{fixture['mutation']}, got "
                f"{got['route']}/{got['mutation']}"
            )


def extract(model: TreeModel, profile: Profile) -> dict:
    """Extract a routing contract and self-checked fixtures from the tree."""
    skill = _entry_skill(model, profile)
    if skill is None or not skill.path.is_file():
        return {"contract": None, "fixtures": [], "source": "description"}
    try:
        contract = derive_contract(skill.path)
    except SystemExit:
        return {"contract": None, "fixtures": [], "source": "description"}
    fixtures = _fixtures_for(contract)
    _self_check(contract, fixtures)
    return {"contract": contract, "fixtures": fixtures, "source": "grammar"}
