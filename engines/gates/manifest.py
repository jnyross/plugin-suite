"""Manifest and skill-frontmatter checks ported from the template validator."""

import re

from contracts.finding import Finding

SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
ALLOWED_FIELDS = {"$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "extensions"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

NAME = "manifest"


def _rel(path, root):
    return path.relative_to(root).as_posix()


def run(model, profile) -> list[Finding]:
    findings: list[Finding] = []
    if model.manifest is None:
        return [Finding("manifest-schema", "error", "plugin.json", "missing or unparsable root plugin.json")]
    m = model.manifest
    if m.get("$schema") != SCHEMA:
        findings.append(Finding("manifest-schema", "error", "plugin.json", f"$schema must be {SCHEMA}"))
    if not NAME_RE.fullmatch(str(m.get("name", ""))):
        findings.append(Finding("manifest-name", "error", "plugin.json", f"name {m.get('name', '')!r} must be lowercase hyphen-case"))
    if not VERSION_RE.fullmatch(str(m.get("version", ""))):
        findings.append(Finding("manifest-version", "error", "plugin.json", f"version {m.get('version', '')!r} must be semver x.y.z"))
    for field_name in ("description", "license"):
        if not isinstance(m.get(field_name), str) or not m[field_name]:
            findings.append(Finding("manifest-field", "error", "plugin.json", f"{field_name} must be a non-empty string"))
    unknown = sorted(set(m) - ALLOWED_FIELDS)
    if unknown:
        findings.append(Finding("manifest-unknown", "error", "plugin.json", f"unsupported fields: {', '.join(unknown)}"))

    seen: dict[str, str] = {}
    for skill in model.skills:
        rel = _rel(skill.path, model.root)
        name = skill.frontmatter.get("name", "")
        if not name or not skill.frontmatter.get("description"):
            findings.append(Finding("skill-frontmatter", "error", rel, "requires name and description frontmatter"))
        if name != skill.path.parent.name:
            findings.append(Finding("skill-folder-mismatch", "error", rel, f"name {name!r} must match folder {skill.path.parent.name!r}"))
        if name in seen:
            findings.append(Finding("skill-duplicate", "error", rel, f"duplicate skill name {name}: {seen[name]} and {rel}"))
        seen[name] = rel
    return findings
