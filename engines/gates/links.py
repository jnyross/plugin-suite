"""Markdown link resolution checks across skills, references, and README."""

import re

from contracts.finding import Finding

NAME = "links"
LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")



def _targets(model):
    root = model.root
    for skill in model.skills:
        yield skill.path
        yield from skill.references
    readme = root / "README.md"
    if readme.is_file():
        yield readme


def run(model, profile) -> list[Finding]:
    findings: list[Finding] = []
    for path in _targets(model):
        rel = path.relative_to(model.root).as_posix()
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.exists():
                findings.append(Finding("broken-link", "error", rel, target))
    return findings
