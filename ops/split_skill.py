"""Split an oversized skill into two at a line boundary."""

from pathlib import Path

NAME = "split_skill"
LARGE_FILE = 300
SPLIT_REQUIRED = 500
_MIN_TAIL = 50


def _source(target: Path, skill: str) -> Path:
    return target / "skills" / skill / "SKILL.md"


def _strip_trailing_blanks(lines: list[str]) -> list[str]:
    out = list(lines)
    while out and not out[-1].strip():
        out.pop()
    return out


def _render(new_name: str, skill: str, tail: list[str]) -> str:
    header = ["---", f"name: {new_name}", f"description: Extracted from {skill}.", "---", "", f"# {new_name}", ""]
    return "\n".join(header + tail) + "\n"


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
    if len(lines) - args["split_at_line"] <= _MIN_TAIL:
        raise ValueError(
            f"{args['skill']} has {len(lines)} lines; splitting at {args['split_at_line']} "
            f"leaves {_MIN_TAIL} or fewer lines behind"
        )
    if (target / "skills" / args["new_name"]).exists():
        raise ValueError(f"skills/{args['new_name']} already exists")


def predict(target: Path, args: dict) -> dict:
    src = _source(target, args["skill"])
    lines = src.read_text(encoding="utf-8").splitlines()
    head = _strip_trailing_blanks(lines[: args["split_at_line"]])
    tail = lines[args["split_at_line"] :]
    old_skills = len(list((target / "skills").glob("*/SKILL.md")))
    changed = {"skills": {"old": old_skills, "new": old_skills + 1}}
    before = _severities(_line_counts(target))
    after_counts = _line_counts(target)
    del after_counts[src]
    after_counts[src] = len(head)
    rendered = _render(args["new_name"], args["skill"], tail)
    after_counts[target / "skills" / args["new_name"] / "SKILL.md"] = len(rendered.splitlines())
    after = _severities(after_counts)
    severity = {k: {"old": v, "new": after[k]} for k, v in before.items() if v != after[k]}
    return {"changed": changed, "severity": severity}


def apply(target: Path, args: dict) -> str:
    src = _source(target, args["skill"])
    lines = src.read_text(encoding="utf-8").splitlines()
    tail = lines[args["split_at_line"] :]
    src.write_text("\n".join(_strip_trailing_blanks(lines[: args["split_at_line"]])) + "\n", encoding="utf-8")
    dest = target / "skills" / args["new_name"]
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text(_render(args["new_name"], args["skill"], tail), encoding="utf-8")
    return f"split {args['skill']} at line {args['split_at_line']}: moved {len(tail)} lines to {args['new_name']}"
