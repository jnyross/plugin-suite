"""Op: remove duplicated guidance lines from non-canonical reference files."""

import re
from pathlib import Path

NAME = "dedup_guidance"

MARKER = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
MIN_LEN = 45


def _normalize(line: str) -> str:
    return MARKER.sub("", line).strip().lower()


def _instruction_files(target: Path) -> dict[str, set[str]]:
    """Map each normalized instruction (>=45 chars, non-header) to the files containing it."""
    out: dict[str, set[str]] = {}
    for ref in sorted((target / "skills").glob("*/references/*.md")):
        rel = ref.relative_to(target).as_posix()
        for line in ref.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                continue
            norm = _normalize(line)
            if len(norm) >= MIN_LEN:
                out.setdefault(norm, set()).add(rel)
    return out


def preconditions(target: Path, args: dict) -> None:
    parts = Path(args["canonical"]).parts
    if len(parts) < 4 or parts[0] != "skills" or parts[2] != "references":
        raise ValueError(f"canonical {args['canonical']!r} must sit under skills/*/references/")
    if not (target / args["canonical"]).is_file():
        raise ValueError(f"canonical {args['canonical']!r} does not exist")
    if not args["duplicates"]:
        raise ValueError("duplicates list must not be empty")
    needle = args["line_substr"].lower()
    for rel in args["duplicates"]:
        path = target / rel
        if not path.is_file():
            raise ValueError(f"duplicate {rel!r} does not exist")
        if not any(needle in _normalize(line) for line in path.read_text(encoding="utf-8").splitlines()):
            raise ValueError(f"duplicate {rel!r} contains no line matching {args['line_substr']!r}")


def predict(target: Path, args: dict) -> dict:
    needle = args["line_substr"].lower()
    duplicates = set(args["duplicates"])
    instructions = _instruction_files(target)
    proposals = sum(1 for files in instructions.values() if len(files) >= 2)
    # An instruction stops being a proposal iff it matches the substring (so every
    # occurrence in duplicates is removed) and at most one untouched file keeps it.
    eliminated = sum(
        1
        for norm, files in instructions.items()
        if len(files) >= 2 and needle in norm and len(files - duplicates) <= 1
    )
    return {"severity": {"proposal": proposals - eliminated}}


def apply(target: Path, args: dict) -> str:
    needle = args["line_substr"].lower()
    removed = 0
    for rel in args["duplicates"]:
        path = target / rel
        kept = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if needle in _normalize(line):
                removed += 1
                continue
            kept.append(line)
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return f"removed {removed} duplicated line(s) across {len(args['duplicates'])} duplicate file(s)"
