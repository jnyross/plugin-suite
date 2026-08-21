# plugin-suite

Doctor and creator suite for [Agent Plugins 1.0.0](https://agent-plugins.org/specification) targets.

This repository is itself an [Agent Plugins 1.0.0](https://agent-plugins.org/specification) plugin: root [`plugin.json`](plugin.json) is the portable manifest, and [`skills/`](skills) wraps the CLI as agent-invocable skills. Point any compatible client (Codex, Cursor, other Agent Plugins adopters) at this repository to install it.

- `python3 cli.py gates <path>` — run all profile-applicable gates, print findings + snapshot.
- `python3 cli.py doctor <path>` — read-only diagnosis: gate findings ranked, judge advisories marked, restructure recommendations as predicted-delta plans.
- `python3 cli.py create` — grilling interview → Spec → scaffolded plugin that passes gates at birth.
- `python3 cli.py diff <a> <b>` — delta between two snapshots.

Stdlib-only Python 3. See `PLAN.md` for architecture, primitives, and phase ladder. Tests: `python3 -m unittest discover -s tests`.

## Releases and updates

Every push to `main` cuts a release automatically: `scripts/release.py` bumps the version in both manifests from commits since the last tag (`feat`/`[minor]` → minor, `BREAKING CHANGE` or `feat!`/`fix!` → major, anything else → patch), then the workflow tags `vX.Y.Z` and publishes a GitHub Release. Installed clients pick it up on marketplace refresh:

```bash
codex plugin marketplace upgrade plugin-suite
codex plugin add plugin-suite@plugin-suite
```

## Install

The repository is dual-packaged: root [`plugin.json`](plugin.json) is the portable Agent Plugins 1.0.0 manifest, and the Codex-native manifests (`.agents/plugins/marketplace.json` + `.codex-plugin/plugin.json`) make it a first-class Codex marketplace.

```bash
codex plugin marketplace add jnyross/plugin-suite --ref main
codex plugin add plugin-suite@plugin-suite
```

Other Agent Plugins 1.0.0 clients: point them at the repository or directory; the root manifest is the portable contract.

Bundled skills:

- `plugin-doctor` — "look at this plugin/skill and tell me if it's good"; restructure recommendations; approved applies with rollback proof.
- `plugin-creator` — "I have an idea" → grilling interview → tested spec → scaffolded plugin that passes every gate at birth.

The Python CLI stays the authoritative surface; the skills only wrap it.
