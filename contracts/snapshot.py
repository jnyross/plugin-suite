"""Snapshot metrics, construction from a tree scan, and diffing."""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

GATES_VERSION = "1"


@dataclass
class Snapshot:
    generated_at: str
    profile_kind: str
    gates_version: str
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "profile_kind": self.profile_kind,
            "gates_version": self.gates_version,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        return cls(
            generated_at=data["generated_at"],
            profile_kind=data["profile_kind"],
            gates_version=data["gates_version"],
            metrics=data["metrics"],
        )


def _count_fixtures(model) -> int:
    if model.fixtures_path is None:
        return 0
    try:
        with open(model.fixtures_path, encoding="utf-8") as fh:
            cases = json.load(fh)
    except (OSError, ValueError):
        return 0
    return len(cases) if isinstance(cases, list) else 0


def _largest_files(model) -> list[list]:
    files: list[tuple[int, str]] = []
    for node in model.skills:
        rel = node.path.relative_to(model.root).as_posix()
        files.append((node.body_lines, rel))
        for ref in node.references:
            try:
                lines = len(ref.read_text(encoding="utf-8").splitlines())
            except OSError:
                lines = 0
            files.append((lines, ref.relative_to(model.root).as_posix()))
    files.sort(key=lambda item: (-item[0], item[1]))
    return [[rel, lines] for lines, rel in files[:5]]


def build_snapshot(model, profile, findings, extra_metrics=None) -> Snapshot:
    extra = extra_metrics or {}
    severities = Counter(f.severity for f in findings)
    return Snapshot(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        profile_kind=profile.kind,
        gates_version=GATES_VERSION,
        metrics={
            "skills": len(model.skills),
            "references": sum(len(node.references) for node in model.skills),
            "routes": extra.get("routes", 0),
            "fixtures": _count_fixtures(model),
            "findings_by_severity": dict(severities),
            "largest_files": _largest_files(model),
        },
    )


def diff(old: Snapshot, new: Snapshot) -> dict:
    changed = {}
    for key in set(old.metrics) | set(new.metrics):
        if key == "findings_by_severity":
            continue
        before, after = old.metrics.get(key), new.metrics.get(key)
        if before != after:
            changed[key] = {"old": before, "new": after}
    old_sev = old.metrics.get("findings_by_severity") or {}
    new_sev = new.metrics.get("findings_by_severity") or {}
    severity = {}
    for sev in set(old_sev) | set(new_sev):
        before, after = old_sev.get(sev, 0), new_sev.get(sev, 0)
        if before != after:
            severity[sev] = {"old": before, "new": after}
    return {"changed": changed, "severity": severity}
