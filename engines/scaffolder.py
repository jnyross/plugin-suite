"""Scaffolder: grow a validated Spec into a green-at-birth plugin tree."""

import json
import re
from pathlib import Path

from contracts.spec import Spec
from engines.snapshot import collect

SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
POLICY_MEANING = {
    "read_only": "no tracked-file edits",
    "scoped": "only requested surface",
    "broad": "requires explicit approval",
}
INVESTIGATE_TOKENS = frozenset(
    "analyze assess audit diagnose explain inspect investigate review understand".split()
)
CHANGE_TOKENS = frozenset(
    "add build change create delete edit fix implement refactor remove repair update write".split()
)
APPROVE_TOKENS = frozenset("approve broaden escalate extend override".split())
WORD = re.compile(r"[a-z]+(?:-[a-z]+)?")
SENTENCE_SPLIT = re.compile(r"[.!?\n;]")
POLITE_DIRECT = re.compile(r"\b(?:can|could|would|will)\s+you\b")
READ_ONLY_MARKERS = (
    "read-only", "readonly", "do not change", "don't change", "no edits", "without editing",
)
QUESTION_WORDS = {"how", "why", "what", "when", "where", "which", "who", "whose", "whom"}
ADVISORY = re.compile(r"(?:should|shall|do|does|did|is|are|am|may|might)\s+(?:i|we)\b")
DETERMINERS = {"this", "that", "these", "those", "the", "a", "an"}


def _expected(request: str, policy: str) -> tuple[str, str]:
    """Fixture heuristic, documented: mirrors engines.routing_contract semantics
    over the scaffolder's fixed vocabularies. A request is change/scoped when it
    carries a change verb outside question form (or via a polite direct ask);
    approve/scoped for approval verbs; otherwise investigation/none under the
    investigate route -- or fallback/none when no vocabulary word appears.
    Deterministic so generated fixtures replay identically in the evaluation gate.
    """
    lowered = request.lower()
    words = set(WORD.findall(lowered))
    if any(marker in lowered for marker in READ_ONLY_MARKERS):
        return _read_only_route(words)
    polite_direct = bool(POLITE_DIRECT.search(lowered))
    question = imperative = False
    change_candidates: set[str] = set()
    approve_candidates: set[str] = set()
    for sentence in SENTENCE_SPLIT.split(lowered):
        tokens = WORD.findall(sentence)
        if not tokens:
            continue
        if tokens[0] in QUESTION_WORDS or ADVISORY.match(sentence):
            question = True
        if tokens[0] in CHANGE_TOKENS | APPROVE_TOKENS:
            imperative = True
        for idx, token in enumerate(tokens):
            if idx and tokens[idx - 1] in DETERMINERS:
                continue
            if token in CHANGE_TOKENS:
                change_candidates.add(token)
            elif token in APPROVE_TOKENS:
                approve_candidates.add(token)
    if not polite_direct and question and not imperative:
        return "investigate", "none"
    if policy != "read_only" and change_candidates:
        return "change", "scoped"
    if policy == "broad" and approve_candidates:
        return "approve", "scoped"
    return "investigate", "none"




def _route_bullet(label: str, tokens: frozenset[str], stem: str) -> str:
    vocab = ", ".join(sorted(tokens)[:-1]) + ", or " + sorted(tokens)[-1]
    return f"- Select **{label}** for {vocab}. Read [{stem}.md](references/{stem}.md)."


def _skill_md(spec: Spec) -> str:
    title = " ".join(word.capitalize() for word in spec.name.split("-"))
    lines = [
        "---",
        f"name: {spec.name}",
        f"description: {spec.purpose}",
        "---",
        "",
        f"# {title}",
        "",
        "## Trigger",
        *[f"- {trigger}" for trigger in spec.triggers],
        "",
        "## Non-triggers",
        *[f"- {item}" for item in spec.non_triggers],
        "",
        "## Inputs",
        spec.inputs,
        "",
        "## Mutation policy",
        f"{spec.mutation_policy}: {POLICY_MEANING[spec.mutation_policy]}.",
        "",
        "## Verification",
        *[f"- {check}" for check in spec.verification],
        "",
        "## Boundaries",
        *[f"- {boundary}" for boundary in spec.boundaries],
        "",
        "## Routes",
        _route_bullet("Investigate", INVESTIGATE_TOKENS, "investigate"),
    ]
    if spec.mutation_policy != "read_only":
        lines.append(_route_bullet("Change", CHANGE_TOKENS, "change"))
    if spec.mutation_policy == "broad":
        lines.append(_route_bullet("Approve", APPROVE_TOKENS, "approve"))
    return "\n".join(lines) + "\n"


_INVESTIGATE_MD = """# Investigate playbook

## Trigger

Read-only questions, explanations, reviews, and diagnoses.

## Intent

Build an accurate picture of the current behavior before anyone acts on it.

## Allowed mutations

None. This path never touches tracked files.

## Workflow

- Restate the question in concrete terms.
- Read the relevant sources and note what the evidence actually shows.
- Separate observed facts from informed speculation.
- Name the smallest experiment that would settle open doubt.

## Verification

Every claim traces to a cited file, command output, or reproducible step.

## Output

A short findings summary with evidence links and, when asked, recommended next steps.
"""

_CHANGE_MD = """# Change playbook

## Trigger

Requests that authorize edits within one clearly requested surface.

## Intent

Land the smallest correct modification that satisfies the stated need.

## Allowed mutations

Scoped to the requested surface only; neighboring code stays untouched.

## Workflow

- Pin down the exact surface the requester named.
- Make the minimal edit that satisfies it.
- Re-read the diff and drop anything the request did not cover.

## Verification

Run the checks named in the skill's Verification section before reporting done.

## Output

A summary of changed files, the reasoning per edit, and verification results.
"""

_APPROVE_MD = """# Approve playbook

## Trigger

Work whose blast radius exceeds one requested surface.

## Intent

Let broader actions proceed only behind explicit human approval.

## Allowed mutations

Broad edits, but each batch requires a recorded human go-ahead first.

## Workflow

- Describe the proposed broader action and its blast radius.
- Stop and wait for explicit human approval before executing.
- Execute only the approved scope and log each applied step.

## Verification

The approval record must precede any broad mutation, and checks must pass after.

## Output

An approval ledger entry plus the change summary and verification results.
"""


def _fixtures(spec: Spec) -> list[dict]:
    cases = []
    for idx, trigger in enumerate(spec.triggers):
        route, mutation = _expected(trigger, spec.mutation_policy)
        cases.append({
            "id": f"{spec.name}-{idx + 1}",
            "request": trigger,
            "route": route,
            "mutation": mutation,
        })
    return cases


_README = """# {title}

{purpose}

Validate the tree at any time with `python3 cli.py gates <plugin-dir>` from the
plugin-suite checkout; the routing fixtures under tests/fixtures must keep passing.
"""


def scaffold(spec: Spec, dest: Path) -> Path:
    """Build a green-at-birth Agent Plugins 1.0.0 tree from spec at dest."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"destination {dest} is not empty")
    skill_dir = dest / "skills" / spec.name
    refs = skill_dir / "references"
    refs.mkdir(parents=True, exist_ok=True)
    (dest / "plugin.json").write_text(json.dumps({
        "$schema": SCHEMA,
        "name": spec.name,
        "version": "0.1.0",
        "description": spec.purpose,
        "license": "MIT",
    }, indent=2) + "\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(_skill_md(spec), encoding="utf-8")
    (refs / "investigate.md").write_text(_INVESTIGATE_MD, encoding="utf-8")
    if spec.mutation_policy != "read_only":
        (refs / "change.md").write_text(_CHANGE_MD, encoding="utf-8")
    if spec.mutation_policy == "broad":
        (refs / "approve.md").write_text(_APPROVE_MD, encoding="utf-8")
    fixture_dir = dest / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "router_cases.json").write_text(
        json.dumps(_fixtures(spec), indent=2) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(
        _README.format(title=spec.name.replace("-", " ").title(), purpose=spec.purpose),
        encoding="utf-8")
    _, _, findings, _ = collect(dest)
    blocking = [f for f in findings if f.severity == "error" or f.code == "evaluation-failure"]
    if blocking:
        detail = "\n".join(f"  {f.code} ({f.severity}) {f.path}: {f.evidence}" for f in blocking)
        raise ValueError(f"scaffold is not green at birth:\n{detail}")
    return dest
