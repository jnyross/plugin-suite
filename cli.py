"""Suite command-line interface: gates and diff."""

import argparse
import json
from pathlib import Path

from contracts.finding import SEVERITIES
from engines import snapshot

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

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
