"""Gate registry and runner."""
from engines.gates import duplication, evaluation, leakage, links, manifest, routing, size

GATES = (manifest, links, leakage, size, duplication, routing, evaluation)


def applicable(profile):
    return [gate for gate in GATES if gate.NAME in profile.gates]


def run_gates(model, profile):
    findings = []
    for gate in applicable(profile):
        findings.extend(gate.run(model, profile))
    return findings
