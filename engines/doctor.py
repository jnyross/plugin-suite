"""Read-only doctor: snapshot, behavioral extraction, and advisory judgment."""

from pathlib import Path

from contracts.finding import Finding
from engines import extractor, judge, snapshot

_SUGGESTIONS = {
    "split-required": "split the file into focused skills (op: split_skill)",
    "large-file": "consider splitting after growth",
    "duplicate-guidance": "deduplicate shared guidance (op: dedup_guidance)",
    "unreachable-playbook": "link the playbook from the router or remove it",
    "missing-evaluation": "add fixture coverage for the route",
}
_FIX_PREFIXES = ("broken", "manifest", "skill")


def _suggestion(finding: Finding) -> str:
    code = finding.code
    if code in _SUGGESTIONS:
        return _SUGGESTIONS[code]
    if code.startswith("judge-") or code == "extracted-fixture-failure":
        return "review advisory"
    if any(code.startswith(prefix) for prefix in _FIX_PREFIXES):
        return "fix before shipping"
    return "review finding"


def recommend(findings: list[Finding]) -> list[str]:
    """One recommendation line per finding, ordered like the findings list."""
    return [
        f"[{finding.severity}] {finding.code} {finding.path} — {_suggestion(finding)}"
        for finding in findings
    ]


def diagnose(root: Path, adapter=None) -> dict:
    """Run snapshot gates, extraction self-checks, and the advisory judge."""
    model, profile, gate_findings, snap = snapshot.collect(root)
    extraction = extractor.extract(model, profile)
    findings = list(gate_findings)
    contract, fixtures = extraction["contract"], extraction["fixtures"]
    if contract and fixtures:
        for fixture in fixtures:
            got = contract.classify(fixture["request"])
            if got["route"] != fixture["route"] or got["mutation"] != fixture["mutation"]:
                findings.append(
                    Finding(
                        "extracted-fixture-failure",
                        "error",
                        fixture["id"],
                        f"expected {fixture['route']}/{fixture['mutation']}, "
                        f"got {got['route']}/{got['mutation']}",
                        source="extractor",
                    )
                )
    findings.extend(judge.check(model, profile, adapter=adapter))
    return {
        "root": str(root),
        "profile": {"kind": profile.kind, "entry": profile.entry},
        "findings": findings,
        "snapshot": snap.to_dict(),
        "extraction": {
            "source": extraction["source"],
            "routes": len(contract.routes) if contract else 0,
            "generated_fixtures": len(fixtures),
        },
    }
