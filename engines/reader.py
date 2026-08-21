"""Read a plugin target tree into a TreeModel."""

import json
import re
from pathlib import Path

from contracts.tree import SkillNode, TreeModel

_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
_EXCLUDED_DIRS = {".git", "reports", "__pycache__", ".suite"}
_EXCLUDED_FILES = {"plugin.json", "SKILL.md"}


def _frontmatter(lines: list[str]) -> dict:
    if len(lines) < 2 or lines[0] != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    meta: dict = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta


def _read_skill(path: Path) -> SkillNode:
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = _frontmatter(lines)
    skill_dir = path.parent
    references_dir = skill_dir / "references"
    text = "\n".join(lines)
    return SkillNode(
        name=meta.get("name") or skill_dir.name,
        path=path,
        frontmatter=meta,
        body_lines=len(lines),
        links=list(_LINK.findall(text)),
        references=sorted(references_dir.glob("*.md")) if references_dir.is_dir() else [],
    )


def _other_files(root: Path, skills: list[SkillNode], fixtures_path: Path | None) -> list[str]:
    skill_dirs = [skill.path.parent for skill in skills]
    found: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in (".md", ".json"):
            continue
        rel = path.relative_to(root)
        if any(part in _EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.name in _EXCLUDED_FILES or path == fixtures_path:
            continue
        if any(skill_dir in path.parents for skill_dir in skill_dirs):
            continue
        found.append(rel.as_posix())
    return sorted(found)


def read_tree(root: Path) -> TreeModel:
    """Build a TreeModel for the plugin tree at root."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"no such directory: {root}")
    manifest = None
    plugin_json = root / "plugin.json"
    if plugin_json.is_file():
        try:
            data = json.loads(plugin_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            manifest = data
    candidate = root / "tests" / "fixtures" / "router_cases.json"
    fixtures_path = candidate if candidate.is_file() else None
    skills_root = root / "skills"
    skill_files = sorted(skills_root.glob("*/SKILL.md")) if skills_root.is_dir() else []
    if not skill_files and (root / "SKILL.md").is_file():
        skill_files = [root / "SKILL.md"]
    skills = [_read_skill(path) for path in skill_files]
    return TreeModel(
        root=root,
        manifest=manifest,
        skills=skills,
        fixtures_path=fixtures_path,
        other_files=_other_files(root, skills, fixtures_path),
    )
