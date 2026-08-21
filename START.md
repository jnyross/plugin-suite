# Start Here: plugin-suite

Read this first in a new agent session, then inspect `AGENTS.md`, `README.md`, `.project.json`, and `git status`.

## Goal

Composable doctor/creator suite for Agent Plugins 1.0.0 targets: deterministic gates, predicted-delta plans, proven reversible transformations.

## Current state

- Status: active
- Stage: building
- Summary: Composable doctor/creator suite for Agent Plugins 1.0.0 targets: deterministic gates, predicted-delta plans, proven reversible transformations.

## Next action

All six PLAN.md phases shipped and committed. Run `python3 cli.py doctor <target>` / `create` on real work; extend ops and rubrics from usage evidence.

## Decisions and constraints

- Target v1: Agent Plugins 1.0.0 only (profiles: single-skill, collection, router-plugin).
- Stdlib-only Python 3; Judge is the only LLM-dependent component, advisory-only behind an injectable adapter.
- Invariants: predicted-delta plans, reversible ops, no mutation without approval, read-only by default.
- Authoritative architecture and phase ladder: `PLAN.md`.

## Resume checklist

1. Read the files named above.
2. Inspect recent Git history and uncommitted changes.
3. Confirm the recorded next action still matches reality.
4. Update `.project.json` and the registry when project state changes.
