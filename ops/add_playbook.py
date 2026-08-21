"""Op: append a routed playbook with vocabulary, a stub body, and self-checking fixtures."""

import json
import re
import sys
from pathlib import Path

from engines.routing_contract import derive_contract  # noqa: E402

NAME = "add_playbook"

SELECT = "- Select **"
TOKEN = "[a-z]+(?:-[a-z]+)?"


def _entry(target: Path) -> Path:
    routers = [
        path
        for path in sorted((target / "skills").glob("*/SKILL.md"))
        if SELECT in path.read_text(encoding="utf-8")
    ]
    if len(routers) != 1:
        raise ValueError(f"expected exactly one router skill with route bullets, found {len(routers)}")
    return routers[0]

def _fixtures_path(target: Path) -> Path:
    return target / "tests" / "fixtures" / "router_cases.json"


def _cases(path: Path) -> list:
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"unparsable fixtures at {path}") from exc
    if not isinstance(cases, list):
        raise ValueError(f"fixtures at {path} must be a JSON list")
    return cases


def preconditions(target: Path, args: dict) -> None:
    if not (target / "plugin.json").is_file():
        raise ValueError("no root plugin.json")
    skill_md = _entry(target)
    for token in args["vocab"]:
        import re

        if not re.fullmatch(TOKEN, token):
            raise ValueError(f"invalid vocabulary token {token!r}")
    stem = args["stem"]
    if (skill_md.parent / "references" / f"{stem}.md").exists():
        raise ValueError(f"playbook {stem!r} already exists")
    if not _fixtures_path(target).is_file():
        raise ValueError(f"no fixture corpus at {_fixtures_path(target)}")


def _route_count(skill_md: Path) -> int:
    return sum(1 for line in skill_md.read_text(encoding="utf-8").splitlines() if SELECT in line)


def predict(target: Path, args: dict) -> dict:
    old_routes = _route_count(_entry(target))
    old_fixtures = len(_cases(_fixtures_path(target)))
    return {"changed": {"routes": old_routes + 1, "fixtures": old_fixtures + 4}}


def _bullet(vocab: list[str], stem: str) -> str:
    label = stem.replace("-", " ").title()
    joined = vocab[0] if len(vocab) == 1 else f"{', '.join(vocab[:-1])}, or {vocab[-1]}"
    return f"- Select **{label}** for {joined}. Read [{stem}.md](references/{stem}.md)."


def _stub(vocab: list[str], stem: str) -> str:
    label = stem.replace("-", " ").title()
    tokens = ", ".join(vocab)
    return (
        f"# {label} Playbook\n"
        "\n"
        "## Trigger\n"
        "\n"
        f"Select this playbook for {tokens} requests that authorize scoped edits.\n"
        "\n"
        "## Intent\n"
        "\n"
        f"Deliver the requested {label.lower()} outcome through the least disruptive edit set.\n"
        "\n"
        "## Workflow\n"
        "\n"
        f"1. Confirm the request names a concrete {vocab[0]} target before editing.\n"
        "2. Stage the edit so the whole unit can be reverted in one motion.\n"
        "3. Prove the result with a check tied to the trigger vocabulary.\n"
        "\n"
        "## Output\n"
        "\n"
        "A scoped diff plus recorded evidence that the triggered behavior now holds.\n"
        "\n"
        "## Boundaries\n"
        "\n"
        "Never edit outside the scope the request authorizes.\n"
    )


def _new_cases(contract_stem: str, vocab: list[str], stem: str) -> list[dict]:
    token = vocab[0]
    return [
        {"id": f"{stem}-positive", "request": f"Please {token} the module.", "route": stem, "mutation": "scoped"},
        {
            "id": f"{stem}-readonly",
            "request": f"Explain the {stem} process but do not change anything.",
            "route": contract_stem,
            "mutation": "none",
        },
        {"id": f"{stem}-dual", "request": f"Investigate and {token} the fix.", "route": stem, "mutation": "scoped"},
        {"id": f"{stem}-ambiguous", "request": f"Get the {token} ready.", "route": "fallback", "mutation": "none"},
    ]


def apply(target: Path, args: dict) -> str:
    vocab: list[str] = args["vocab"]
    stem: str = args["stem"]
    skill_md = _entry(target)
    read_only_stem = derive_contract(skill_md).routes[0].stem

    lines = skill_md.read_text(encoding="utf-8").splitlines()
    last = max(idx for idx, line in enumerate(lines) if SELECT in line)
    lines.insert(last + 1, _bullet(vocab, stem))
    skill_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    references = skill_md.parent / "references"
    (references / f"{stem}.md").write_text(_stub(vocab, stem), encoding="utf-8")

    fixtures_path = _fixtures_path(target)
    cases = _cases(fixtures_path) + _new_cases(read_only_stem, vocab, stem)
    fixtures_path.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    return f"added playbook {stem} ({len(vocab)} vocabulary tokens, 4 fixtures)"
