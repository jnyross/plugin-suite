"""Client-specific leakage detection ported from validator and health audit."""

from contracts.finding import Finding

MARKERS = (".cursor-plugin", ".codex-plugin", ".claude-plugin", "~/.cursor", "Cursor Task")
CLIENT_PATHS = {".cursor-plugin", ".codex-plugin", ".claude-plugin", "agents", "commands", "hooks"}

NAME = "leakage"


def run(model, profile) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(CLIENT_PATHS):
        if (model.root / path).exists():
            findings.append(Finding("client-path", "error", path, "client-specific path leaks into portable root"))
    for skill in model.skills:
        for text_path in [skill.path, *skill.references]:
            text = text_path.read_text(encoding="utf-8")
            rel = text_path.relative_to(model.root).as_posix()
            for marker in MARKERS:
                if marker in text:
                    findings.append(Finding("client-leakage", "warning", rel, marker))
    return findings
