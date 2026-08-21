#!/usr/bin/env python3
"""Cut a release: bump the version in both manifests from commits since the last tag.

Bump rules (first match wins), evaluated over commit subjects since the last tag:
- a subject containing BREAKING CHANGE or starting with feat!/fix!  -> major
- a subject starting with feat or containing [minor]                -> minor
- otherwise                                                         -> patch
Every non-empty range cuts a release. Prints the resulting version.
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (ROOT / "plugin.json", ROOT / ".codex-plugin" / "plugin.json")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def current_version() -> str:
    return json.loads(MANIFESTS[0].read_text(encoding="utf-8"))["version"]


def commits_since_last_tag() -> list[str]:
    try:
        rng = f"{git('describe', '--tags', '--abbrev=0')}..HEAD"
    except subprocess.CalledProcessError:
        rng = "HEAD"
    out = git("log", "--format=%s", rng)
    return [line for line in out.splitlines() if line.strip()]


def bump_level(subjects: list[str]) -> str:
    if any("BREAKING CHANGE" in subject or re.match(r"^(feat|fix)!", subject) for subject in subjects):
        return "major"
    if any(subject.startswith("feat") or "[minor]" in subject for subject in subjects):
        return "minor"
    return "patch"


def bumped(version: str, level: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def main() -> int:
    subjects = commits_since_last_tag()
    version = current_version()
    if not subjects:
        print(version)
        return 0
    new_version = bumped(version, bump_level(subjects))
    for manifest in MANIFESTS:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = new_version
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
