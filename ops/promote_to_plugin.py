"""Op: promote a bare skill collection into a plugin by writing a root manifest."""

import json
import re
from pathlib import Path

NAME = "promote_to_plugin"

SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)


def _skills(target: Path) -> list[Path]:
    return sorted((target / "skills").glob("*/SKILL.md"))


def _description(skill_md: Path) -> str | None:
    match = FRONTMATTER.match(skill_md.read_text(encoding="utf-8"))
    if not match:
        return None
    for line in match.group(1).splitlines():
        if line.startswith("description:"):
            return line[len("description:"):].strip() or None
    return None


def _manifest_name(target: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", target.name.lower()).strip("-")


def preconditions(target: Path, args: dict) -> None:
    if (target / "plugin.json").exists():
        raise ValueError("root plugin.json already exists")
    if not _skills(target):
        raise ValueError("no skills/*/SKILL.md found")


def predict(target: Path, args: dict) -> dict:
    return {}


def apply(target: Path, args: dict) -> str:
    skills = _skills(target)
    description = next((d for d in (_description(s) for s in skills) if d), target.name)
    name = _manifest_name(target)
    manifest = {
        "$schema": SCHEMA,
        "name": name,
        "version": "0.1.0",
        "description": description,
        "license": "MIT",
    }
    (target / "plugin.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    return f"wrote plugin.json (name={name}, description from first skill)"
