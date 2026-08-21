"""Dataclasses describing a plugin target tree."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillNode:
    name: str
    path: Path
    frontmatter: dict
    body_lines: int
    links: list[str]
    references: list[Path]


@dataclass
class TreeModel:
    root: Path
    manifest: dict | None
    skills: list[SkillNode] = field(default_factory=list)
    fixtures_path: Path | None = None
    other_files: list[str] = field(default_factory=list)
