# plugin-suite

Doctor and creator suite for [Agent Plugins 1.0.0](https://agent-plugins.org/specification) targets.

This repository is itself an [Agent Plugins 1.0.0](https://agent-plugins.org/specification) plugin: root [`plugin.json`](plugin.json) is the portable manifest, and [`skills/`](skills) wraps the CLI as agent-invocable skills. Point any compatible client (Codex, Cursor, other Agent Plugins adopters) at this repository to install it.

- `python3 cli.py gates <path>` — run all profile-applicable gates, print findings + snapshot.
- `python3 cli.py doctor <path>` — read-only diagnosis: gate findings ranked, judge advisories marked, restructure recommendations as predicted-delta plans.
- `python3 cli.py create` — grilling interview → Spec → scaffolded plugin that passes gates at birth.
- `python3 cli.py diff <a> <b>` — delta between two snapshots.

Stdlib-only Python 3. See `PLAN.md` for architecture, primitives, and phase ladder. Tests: `python3 -m unittest discover -s tests`.

## Install

Add the repository as a marketplace entry or point your client at the directory — the root manifest makes it installable anywhere the Agent Plugins 1.0.0 contract is supported. Bundled skills:

- `plugin-doctor` — "look at this plugin/skill and tell me if it's good"; restructure recommendations; approved applies with rollback proof.
- `plugin-creator` — "I have an idea" → grilling interview → tested spec → scaffolded plugin that passes every gate at birth.

The Python CLI stays the authoritative surface; the skills only wrap it.
