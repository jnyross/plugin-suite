"""Suite command-line interface: gates, diff, doctor, and create."""

import argparse
import json
import sys
from pathlib import Path

from contracts.finding import SEVERITIES
from engines import doctor, interviewer, scaffolder, snapshot

_RANK = {sev: rank for rank, sev in enumerate(SEVERITIES)}


def _gates(args: argparse.Namespace) -> int:
    _, profile, findings, snap = snapshot.collect(Path(args.path))
    entry = f" entry={profile.entry}" if profile.entry else ""
    print(f"profile: {profile.kind}{entry}")
    ordered = sorted(findings, key=lambda f: (_RANK[f.severity], f.code, f.path))
    for finding in ordered:
        print(f"{finding.severity.upper()} {finding.code} {finding.path} — {finding.evidence}")
    print(json.dumps(snap.metrics))
    if args.out:
        path = snapshot.save(snap, Path(args.out))
        print(f"snapshot: {path}")
    return 1 if any(f.severity == "error" for f in findings) else 0


def _diff(args: argparse.Namespace) -> int:
    old = snapshot.load(Path(args.old))
    new = snapshot.load(Path(args.new))
    print(json.dumps(snapshot.delta(old, new)))
    return 0


def _doctor(args: argparse.Namespace) -> int:
    report = doctor.diagnose(Path(args.path))
    findings = report["findings"]
    payload = {**report, "findings": [f.to_dict() for f in findings]}
    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "doctor-report.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    if args.json:
        print(json.dumps(payload))
        return 0
    entry = f" entry={report['profile']['entry']}" if report["profile"]["entry"] else ""
    print(f"profile: {report['profile']['kind']}{entry}")
    for finding in sorted(findings, key=lambda f: (_RANK[f.severity], f.code, f.path)):
        tag = "" if finding.source == "gate" else f" [{finding.source}]"
        print(f"{finding.severity.upper()} {finding.code} {finding.path} — {finding.evidence}{tag}")
    print("## Recommendations")
    for line in doctor.recommend(findings):
        print(line)
    return 1 if any(f.severity == "error" and f.source != "judge" for f in findings) else 0

def _create(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    answers: list[str] | None = None
    if args.answers:
        try:
            raw = json.loads(Path(args.answers).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"create: cannot read answers file {args.answers}: {exc}", file=sys.stderr)
            return 1
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            print(f"create: {args.answers} must contain a JSON array of strings", file=sys.stderr)
            return 1
        answers = raw
    try:
        interview = interviewer.load(state_dir)
    except (OSError, ValueError, KeyError):
        interview = interviewer.Interview(answers=answers)
    if answers is not None:
        interview.answers = list(answers)
    spec = interview.run()
    state_path = interviewer.save(state_dir, interview)
    try:
        spec.validate()
    except ValueError as exc:
        print(f"create: interview incomplete ({exc}); state saved at {state_path}", file=sys.stderr)
        return 1
    dest = Path(args.dest) if args.dest else Path.cwd() / spec.name
    try:
        scaffolder.scaffold(spec, dest)
    except ValueError as exc:
        print(f"create: {exc}", file=sys.stderr)
        return 1
    _, _, _, snap = snapshot.collect(dest)
    print(f"created: {dest}")
    print(json.dumps(snap.metrics))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plugin-suite")
    sub = parser.add_subparsers(dest="command", required=True)

    gates = sub.add_parser("gates", help="run profile gates on a plugin tree")
    gates.add_argument("path", help="plugin tree root")
    gates.add_argument("--out", default=None, help="directory to save the snapshot JSON into")
    gates.set_defaults(fn=_gates)

    diff = sub.add_parser("diff", help="diff two saved snapshots")
    diff.add_argument("old", help="old snapshot JSON")
    diff.add_argument("new", help="new snapshot JSON")
    diff.set_defaults(fn=_diff)

    doc = sub.add_parser("doctor", help="run the read-only health doctor on a plugin tree")
    doc.add_argument("path", help="plugin tree root")
    doc.add_argument("--out", default=None, help="directory to save the JSON report into")
    doc.add_argument("--json", action="store_true", help="print the full report as JSON")
    doc.set_defaults(fn=_doctor)

    create = sub.add_parser("create", help="interview for a Spec and scaffold a green plugin tree")
    create.add_argument("--state-dir", default=".", help="directory holding .suite interview state")
    create.add_argument("--dest", default=None, help="plugin destination directory (default ./<name>)")
    create.add_argument("--answers", default=None, help="JSON file containing an array of answer strings")
    create.set_defaults(fn=_create)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
