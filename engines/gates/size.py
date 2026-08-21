"""File-size gate: flags oversized skill bodies and reference files."""

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.tree import TreeModel

NAME = "size"


def run(model: TreeModel, profile: Profile) -> list[Finding]:
    large = profile.thresholds.get("large_file", 300)
    split = profile.thresholds.get("split_required", 500)
    findings: list[Finding] = []
    for node in model.skills:
        rel = node.path.relative_to(model.root).as_posix()
        if node.body_lines > split:
            findings.append(Finding("split-required", "proposal", rel, f"{node.body_lines} body lines exceeds {split}"))
        elif node.body_lines > large:
            findings.append(Finding("large-file", "warning", rel, f"{node.body_lines} body lines exceeds {large}"))
        for ref in node.references:
            lines = len(ref.read_text(encoding="utf-8").splitlines())
            rel_ref = ref.relative_to(model.root).as_posix()
            if lines > split:
                findings.append(Finding("split-required", "proposal", rel_ref, f"{lines} lines exceeds {split}"))
            elif lines > large:
                findings.append(Finding("large-file", "warning", rel_ref, f"{lines} lines exceeds {large}"))
    return findings
