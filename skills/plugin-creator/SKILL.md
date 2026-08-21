---
name: plugin-creator
description: Interview an idea into a tested specification and scaffold a green-at-birth Agent Plugins 1.0.0 plugin. Use when the user has an idea for a skill or plugin and wants it created properly - with triggers, mutation policy, and verification settled before any code exists.
---

# Plugin Creator

Interview first, scaffold second. The grilling is the product: an idea that cannot state its triggers, mutation policy, and verification checks is not ready to become a plugin.

## Run

Interactive (asks the user directly):

```bash
python3 cli.py create --dest <destination-dir>
```

Scripted (answers supplied as a JSON array of strings; an empty string terminates a multi-line field):

```bash
python3 cli.py create --dest <destination-dir> --answers answers.json
```

## The interview

Questions walk the spec fields in order: name, purpose, trigger example requests, non-triggers, inputs, mutation policy (`read_only` | `scoped` | `broad`), observable verification checks, boundaries. Each field gets at most three attempts; unresolved requirements are recorded as open questions in the saved spec rather than guessed.

State persists at `<state-dir>/.suite/interview.json`, so an interrupted interview resumes with `--state-dir`.

## Output

The scaffolder derives plugin.json, the entry SKILL.md, playbooks from the mutation policy, and behavioral fixtures from the trigger examples - then runs every gate before showing the result. A scaffold that fails any gate is never presented; exit code 1 means the reason is on stderr.

See [../../PLAN.md](../../PLAN.md) for architecture and [../../README.md](../../README.md) for the full CLI surface.
