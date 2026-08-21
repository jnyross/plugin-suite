"""Extract a single guidance line into its own principle skill."""

from pathlib import Path

NAME = "extract_principle"
LARGE_FILE = 300
SPLIT_REQUIRED = 500


def _source(target: Path, skill: str) -> Path:
    return target / "skills" / skill / "SKILL.md"


def _matching_lines(lines: list[str], substr: str) -> list[str]:
    return [line for line in lines if not line.lstrip().startswith("#") and substr in line]


def _remove_one(lines: list[str], line: str) -> list[str]:
    out = list(lines)
    out.pop(out.index(line))
    return out


def _line_counts(target: Path) -> dict[Path, int]:
    counts: dict[Path, int] = {}
    for skill_md in sorted((target / "skills").glob("*/SKILL.md")):
        counts[skill_md] = len(skill_md.read_text(encoding="utf-8").splitlines())
        refs = skill_md.parent / "references"
        if refs.is_dir():
            for ref in sorted(refs.glob("*.md")):
                counts[ref] = len(ref.read_text(encoding="utf-8").splitlines())
    return counts


def _severities(counts: dict[Path, int]) -> dict[str, int]:
    sev = {"warning": 0, "proposal": 0}
    for n in counts.values():
        if n > SPLIT_REQUIRED:
            sev["proposal"] += 1
        elif n > LARGE_FILE:
            sev["warning"] += 1
    return sev


def preconditions(target: Path, args: dict) -> None:
    src = _source(target, args["skill"])
    if not src.is_file():
        raise ValueError(f"no such skill: skills/{args['skill']}/SKILL.md")
    lines = src.read_text(encoding="utf-8").splitlines()
    matches = _matching_lines(lines, args["line_substr"])
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one non-heading line containing {args['line_substr']!r} in "
            f"{args['skill']}, found {len(matches)}"
        )
    if (target / "skills" / args["new_name"]).exists():
        raise ValueError(f"skills/{args['new_name']} already exists")


def predict(target: Path, args: dict) -> dict:
    src = _source(target, args["skill"])
    old_skills = len(list((target / "skills").glob("*/SKILL.md")))
    changed = {"skills": {"old": old_skills, "new": old_skills + 1}}
    before = _severities(_line_counts(target))
    after_counts = _line_counts(target)
    after_counts[src] -= 1
    severity = {k: {"old": v, "new": _severities(after_counts)[k]} for k, v in before.items()}
    severity = {k: pair for k, pair in severity.items() if pair["old"] != pair["new"]}
    return {"changed": changed, "severity": severity}


def apply(target: Path, args: dict) -> str:
    src = _source(target, args["skill"])
    lines = src.read_text(encoding="utf-8").splitlines()
    line = _matching_lines(lines, args["line_substr"])[0]
    src.write_text("\n".join(_remove_one(lines, line)) + "\n", encoding="utf-8")
    dest = target / "skills" / args["new_name"]
    dest.mkdir(parents=True)
    content = "\n".join(
        [
            "---",
            f"name: {args['new_name']}",
            f"description: Principle extracted from {args['skill']}.",
            "---",
            "",
            f"- {line}",
        ]
    )
    (dest / "SKILL.md").write_text(content + "\n", encoding="utf-8")
    return f"extracted principle {args['new_name']} from {args['skill']}"
