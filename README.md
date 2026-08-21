# plugin-suite

Doctor and creator suite for [Agent Plugins 1.0.0](https://agent-plugins.org/specification) targets.

- `python3 cli.py gates <path>` — run all profile-applicable gates, print findings + snapshot.
- `python3 cli.py doctor <path>` — read-only diagnosis: gate findings ranked, judge advisories marked, restructure recommendations as predicted-delta plans.
- `python3 cli.py create` — grilling interview → Spec → scaffolded plugin that passes gates at birth.
- `python3 cli.py diff <a> <b>` — delta between two snapshots.

Stdlib-only Python 3. See `PLAN.md` for architecture, primitives, and phase ladder. Tests: `python3 -m unittest discover -s tests`.
