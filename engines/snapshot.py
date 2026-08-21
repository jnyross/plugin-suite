"""Snapshot collection, persistence, and diffing over contracts.snapshot."""

import json
from datetime import datetime, timezone
from pathlib import Path

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.snapshot import Snapshot, build_snapshot, diff
from contracts.tree import TreeModel
from engines.gates import run_gates
from engines.profiler import infer_profile
from engines.reader import read_tree


def collect(root: Path) -> tuple[TreeModel, Profile, list[Finding], Snapshot]:
    """Scan a plugin tree and build a snapshot from its gates."""
    model = read_tree(root)
    profile = infer_profile(model)
    findings = run_gates(model, profile)
    return model, profile, findings, build_snapshot(model, profile, findings)


def save(snapshot: Snapshot, out_dir: Path, name: str | None = None) -> Path:
    """Write a snapshot as JSON under out_dir; return the file path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if name is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"snapshot-{stamp}.json"
    path = out_dir / name
    path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    return path


def load(path: Path) -> Snapshot:
    """Read a snapshot JSON file back into a Snapshot."""
    return Snapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))


def delta(old: Snapshot, new: Snapshot) -> dict:
    """Diff two snapshots' metrics."""
    return diff(old, new)
