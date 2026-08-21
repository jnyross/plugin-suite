"""Plan application with gate-verified proof and whole-tree rollback."""

import importlib
import shutil
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from contracts.plan import OpCall, Plan
from contracts.snapshot import diff
from engines.snapshot import collect

OPS = ("split_skill", "extract_principle", "promote_to_plugin", "add_playbook", "dedup_guidance")
_BACKUP_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".suite", "reports")


def load_op(name: str):
    """Resolve a registry key to its ops module."""
    if name not in OPS:
        raise ValueError(f"unknown op {name!r}; known ops: {', '.join(OPS)}")
    return importlib.import_module(f"ops.{name}")


def _entry(entry: int | dict) -> dict:
    """Normalize a predicted delta entry to {'old': o, 'new': n}."""
    if isinstance(entry, int):
        return {"old": None, "new": entry}
    return {"old": entry.get("old"), "new": entry.get("new")}


def _merge_predicted(target: Path, calls: list[tuple[str, dict]]) -> dict:
    changed: dict = {}
    severity: dict = {}
    for name, args in calls:
        op = load_op(name)
        op.preconditions(target, args)
        predicted = op.predict(target, args)
        for key, raw in predicted.get("changed", {}).items():
            changed[key] = _entry(raw)
        for sev, raw in predicted.get("severity", {}).items():
            entry = _entry(raw)
            if sev in severity:
                severity[sev]["new"] += entry["new"]
            else:
                severity[sev] = entry
    merged: dict = {}
    if changed:
        merged["changed"] = changed
    if severity:
        merged["severity"] = severity
    return merged


def build_plan(target: Path, calls: list[tuple[str, dict]], rationale: str = "") -> Plan:
    """Validate calls against the live tree and compose a draft plan."""
    target = Path(target)
    return Plan(
        id=f"plan-{secrets.token_hex(4)}",
        target=str(target),
        ops=[OpCall(op=name, args=dict(args), rationale=rationale) for name, args in calls],
        predicted_delta=_merge_predicted(target, calls),
        rollback={"strategy": "whole-tree-backup"},
    )


def approve(plan: Plan) -> None:
    plan.transition("approved")


def verify_predicted(predicted: dict, actual: dict) -> list[str]:
    """Return mismatch strings for every predicted entry not matched by actual."""
    mismatches: list[str] = []
    for key, raw in predicted.get("changed", {}).items():
        want = _entry(raw)
        got = actual.get("changed", {}).get(key)
        if got is None:
            mismatches.append(f"changed[{key}]: predicted {want}, actual unchanged")
            continue
        if want["new"] is not None and got.get("new") != want["new"]:
            mismatches.append(f"changed[{key}].new: predicted {want['new']!r}, actual {got.get('new')!r}")
        if want["old"] is not None and got.get("old") != want["old"]:
            mismatches.append(f"changed[{key}].old: predicted {want['old']!r}, actual {got.get('old')!r}")
    for sev, raw in predicted.get("severity", {}).items():
        want = _entry(raw)
        got = actual.get("severity", {}).get(sev)
        if want["new"] is not None and (got is None or got.get("new") != want["new"]):
            actual_new = got.get("new") if got else "unchanged"
            mismatches.append(f"severity[{sev}].new: predicted {want['new']!r}, actual {actual_new!r}")
        if want["old"] is not None and (got is None or got.get("old") != want["old"]):
            actual_old = got.get("old") if got else "unchanged"
            mismatches.append(f"severity[{sev}].old: predicted {want['old']!r}, actual {actual_old!r}")
    return mismatches


def _restore(backup: Path, target: Path) -> None:
    for child in target.iterdir():
        if child.name in {".git", "__pycache__", ".suite", "reports"}:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    shutil.copytree(backup, target, dirs_exist_ok=True)


def apply(plan: Plan, decision_dir: Path | None = None) -> dict:
    """Apply an approved plan; roll back the whole tree on any failure."""
    if plan.status != "approved":
        raise ValueError(f"plan {plan.id} is {plan.status!r}; only approved plans can be applied")
    target = Path(plan.target)

    _, _, baseline_findings, baseline_snapshot = collect(target)
    baseline_errors = sum(1 for f in baseline_findings if f.severity == "error")

    backup_root = Path(tempfile.mkdtemp(prefix="plan-backup-"))
    backup = backup_root / "tree"
    shutil.copytree(target, backup, ignore=_BACKUP_IGNORE)

    def rolled_back(reason: str, at_op: int) -> dict:
        _restore(backup, target)
        shutil.rmtree(backup_root)
        plan.transition("rolled_back")
        return {"status": "rolled_back", "reason": reason, "at_op": at_op}

    for index, call in enumerate(plan.ops):
        try:
            load_op(call.op).apply(target, call.args)
        except Exception as exc:
            return rolled_back(f"op {call.op!r} failed: {exc}", index)

    _, _, result_findings, result_snapshot = collect(target)
    actual = diff(baseline_snapshot, result_snapshot)
    errors = sum(1 for f in result_findings if f.severity == "error")
    if errors > baseline_errors:
        return rolled_back(
            f"error-severity findings increased: {baseline_errors} -> {errors}", len(plan.ops)
        )
    mismatches = verify_predicted(plan.predicted_delta, actual)
    if mismatches:
        return rolled_back("; ".join(mismatches), len(plan.ops))

    plan.transition("applied")
    out_dir = Path(decision_dir) if decision_dir is not None else target / "decisions"
    out_dir.mkdir(parents=True, exist_ok=True)
    decision = out_dir / f"{plan.id}.md"
    ops_md = "\n".join(f"- `{call.op}` {call.args} — {call.rationale}" for call in plan.ops)
    decision.write_text(
        f"# {plan.id}\n\n"
        f"date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
        f"## Ops\n\n{ops_md}\n\n"
        f"## Predicted\n\n```json\n{plan.predicted_delta}\n```\n\n"
        f"## Actual\n\n```json\n{actual}\n```\n\n"
        f"outcome: applied\n",
        encoding="utf-8",
    )
    plan.decision_ref = str(decision)
    shutil.rmtree(backup_root)
    return {"status": "applied", "actual": actual, "decision": decision}
