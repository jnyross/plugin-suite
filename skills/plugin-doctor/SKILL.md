---
name: plugin-doctor
description: Diagnose any Agent Plugins 1.0.0 plugin or skill directory - structural gates, behavioral extraction, advisory review, and restructure recommendations as predicted-delta plans. Use when asked whether a plugin or skill is any good, how to improve or restructure it, whether it should become a plugin, or to apply an approved restructure.
---

# Plugin Doctor

Diagnose before touching. Every improvement claim must be a measured delta; no mutation without an approved plan.

## Run

From this repository's checkout:

```bash
python3 cli.py doctor <target-path>
```

Read-only by default. The report lists gate findings ranked error > warning > proposal > info, judge advisories tagged `[judge]`, and a Recommendations section mapping findings to transform operations.

## Interpreting

- `error` findings are mechanical defects (broken links, invalid manifest, failing behavioral fixtures) - fix before anything else.
- `warning`/`proposal` findings are sizing and consistency pressure (`large-file`, `split-required`, `duplicate-guidance`, `unreachable-playbook`).
- `[judge]` items are advisory semantic review (description-trigger fit, boundary clarity). They never block; weigh them, do not obey them blindly.

## Applying changes

Only after the user explicitly approves a specific change set:

```bash
python3 - <<'EOF'
from pathlib import Path
import sys
sys.path.insert(0, "<suite-checkout>")
from engines.transformer import build_plan, approve, apply
plan = build_plan(Path("<target>"), [("split_skill", {"skill": "...", "new_name": "...", "split_at_line": 300})], rationale="<user-approved reason>")
approve(plan)
print(apply(plan))
EOF
```

The transformer re-runs every gate after applying: if the measured delta misses the prediction or any new error appears, the tree is restored byte-identical and the plan is marked `rolled_back`. Never edit a target tree by hand when an op exists.

See [../../PLAN.md](../../PLAN.md) for the architecture and [../../README.md](../../README.md) for the full CLI surface.
