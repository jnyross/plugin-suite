"""Advisory-only semantic judge: LLM review of skill quality via pluggable adapter."""

import json
import re
from pathlib import Path

from contracts.finding import Finding
from contracts.profile import Profile
from contracts.tree import TreeModel

RUBRIC_VERSION = "1"
RUBRICS = {
    "description-trigger-fit": "Does each skill description name concrete triggers that would route matching requests to it?",
    "boundary-clarity": "Are the boundaries between overlapping skills stated so routing is unambiguous?",
    "verification-falsifiability": "Do verification instructions state observable outcomes rather than vague assurances?",
    "granularity": "Is any single skill doing too much, such that it should be split or delegated?",
}
BODY_HEAD_LINES = 60
MAX_FINDINGS = 12

PROMPT_TEMPLATE = """You are an advisory reviewer for plugin skill packages. Review the material below against every rubric and report concrete problems.

Rubrics:
{rubrics}

Respond with STRICT JSON only: an array of objects {{"code": "<short-id>", "severity": "warning"|"info", "evidence": "<what you observed>"}} and nothing else. Use at most {max_findings} findings. Return [] when there is nothing to flag. Prefix codes with "judge-".

Material (rubric version {version}):
{material}"""


def _body_head(path: Path, limit: int = BODY_HEAD_LINES) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    return "\n".join(text.splitlines()[:limit])


def _build_prompt(model: TreeModel) -> str:
    rubrics = "\n".join(f"- {rid}: {rule}" for rid, rule in RUBRICS.items())
    chunks: list[str] = []
    if model.manifest:
        desc = model.manifest.get("description")
        if desc:
            chunks.append(f"manifest description: {desc}")
    for node in model.skills:
        rel = node.path.relative_to(model.root).as_posix()
        desc = node.frontmatter.get("description", "")
        chunks.append(f"skill {node.name} ({rel})\ndescription: {desc}\nbody:\n{_body_head(node.path)}")
    return PROMPT_TEMPLATE.format(
        rubrics=rubrics,
        max_findings=MAX_FINDINGS,
        version=RUBRIC_VERSION,
        material="\n\n".join(chunks),
    )


def _parse_array(response: str):
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if not match:
        raise ValueError("no JSON array found")
    return json.loads(match.group(0))


def _skill_path(model: TreeModel, evidence: str) -> str:
    lowered = evidence.lower()
    for node in model.skills:
        if node.name.lower() in lowered:
            return node.path.relative_to(model.root).as_posix()
    return model.root.as_posix()


def check(model: TreeModel, profile: Profile, adapter=None) -> list[Finding]:
    """Run the advisory judge over the tree; returns findings or an availability note."""
    if adapter is None:
        return [Finding("judge-unavailable", "info", str(model.root), "no adapter configured", source="judge")]
    response = adapter(_build_prompt(model))
    try:
        items = _parse_array(response)
        if not isinstance(items, list):
            raise ValueError("payload is not a JSON array")
    except (ValueError, TypeError) as exc:
        head = "\n".join(response.splitlines()[:10])
        return [Finding("judge-unparsable", "info", str(model.root), f"{exc}: {head}", source="judge")]
    findings: list[Finding] = []
    for item in items[:MAX_FINDINGS]:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "judge-uncategorized")
        if not code.startswith("judge-"):
            code = f"judge-{code}"
        severity = item.get("severity")
        if severity not in ("warning", "info"):
            severity = "info"
        evidence = str(item.get("evidence", ""))
        findings.append(Finding(code, severity, _skill_path(model, evidence), evidence, source="judge"))
    return findings[:MAX_FINDINGS]
