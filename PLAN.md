# Plugin Suite — Implementation Plan

Status: in progress (orchestrated build; phases below are the work breakdown)
Origin: Plugin-Template session 2026-08-21; grounded in that repo's working gates.

## Goal

A composable suite where "I have a skill/plugin — what should I do with it?" and "I have an idea — build it with me" both end in **tested, proven** answers: deterministic gates + advisory judgment → recommendation as a predicted-delta plan → human yes/no → implemented with gate-verified proof and rollback safety.

Products (thin compositions):
- **skill doctor / plugin doctor** — observe, diagnose, recommend; optional approved apply.
- **skill creator** — grilling interview → Spec → scaffolded artifact that passes gates at birth.

## Locked decisions

- Home: `~/projects/plugin-suite` (this repo).
- Target v1: Agent Plugins 1.0.0 only. Profiles: `single-skill`, `collection`, `router-plugin`. Other ecosystems = post-v1 adapter profiles.
- Stdlib-only Python 3. The Judge is the sole LLM-dependent component, isolated behind an injectable adapter interface, advisory-only, skippable.
- Surface: CLI (`cli.py`: `gates|doctor|create|diff`) is authoritative; thin managed omp skills wrap it later for conversation UX.

## Invariants (non-negotiable)

1. Deterministic core is authoritative; Judge findings are `warning|info`, never block, always attributed + rubric-versioned.
2. Every improvement claim is a **Delta** (predicted vs measured). Prediction miss ⇒ rollback + recorded learning.
3. No mutation without an approved Plan; every op reversible; every applied Plan leaves a decision record.
4. Read-only by default on target trees; writes opt-in (`--out`, `--apply`).

## Architecture

```
plugin-suite/
  contracts/    tree.py profile.py finding.py snapshot.py spec.py plan.py
  engines/      reader.py profiler.py routing_contract.py
                gates/ (manifest links leakage size duplication routing evaluation)
                extractor.py judge.py transformer.py interviewer.py scaffolder.py snapshot.py
  ops/          split_skill.py extract_principle.py promote_to_plugin.py add_playbook.py dedup_guidance.py
  cli.py        suite gates|doctor|create|diff
  tests/
```

Workspace convention on targets: snapshots/findings → stdout by default, `--out reports/suite/`; applied Plans → `decisions/`. Never writes without flags.

## Contracts

1. **TreeModel** — root, manifest|None, skills[]{name, path, frontmatter, body_lines, links[], references[]}, fixtures_path|None.
2. **Profile** — kind (`single-skill` | `collection` | `router-plugin`) + thresholds `{large_file:300, split_required:500}` + applicable gate list + entry skill name.
3. **Finding** — `{code, severity(error|warning|proposal|info), path, evidence, source, op_hint?}`. Migrates all 8 health_audit codes + validator messages 1:1.
4. **Snapshot/Delta** — `{generated_at, profile_kind, gates_version, metrics{...}}`; Delta = field diff + finding-code multiset diff.
5. **Spec** — `{name, purpose, triggers[](concrete example requests), non_triggers[], inputs, mutation_policy(read_only|scoped|broad), verification[](observable checks), boundaries[], open_questions[]}`.
6. **Plan** — `{id, target, ops[{op, args, rationale}], predicted_delta, rollback, status(draft|approved|applied|rolled_back), decision_ref}`.

## Engines

- **GateRunner** — registry keyed by Profile; ports of `validate_plugin` (manifest/links/leakage) and `health_audit` (size/duplication/routing/evaluation). Routing gate scoped to the *entry* skill's references.
- **routing_contract** — ported `derive_contract`/`Route`/`Contract` from Plugin-Template `scripts/router_contract.py`; parameterized by SKILL.md path.
- **Extractor** — route-bullet grammar present → contract + generated fixture sets per route (positive / read-only / dual-intent / ambiguous). Grammar absent → trigger-fixture stubs from description; Judge proposes expectations, human confirms.
- **Judge** — `judge.check(model, spec=None, adapter=None) -> [Finding(source="judge")]`; rubrics v1: description-trigger fit, boundary clarity, verification falsifiability, granularity. No adapter ⇒ skips with an info finding.
- **Transformer** — `apply(plan)`: per op: preconditions → apply → GateRunner → compare actual vs predicted Delta → error regression or mismatch ⇒ inverse-op rollback, Plan `rolled_back`. Success ⇒ decision markdown + final Snapshot.
- **Ops** — each defines `preconditions / apply / inverse / predicted_delta_fn`: `split_skill`, `extract_principle`, `promote_to_plugin`, `add_playbook`, `dedup_guidance`.
- **Interviewer** — state machine over Spec fields; grilling rules: triggers must be concrete request strings; mutation policy from enum; verification must be observable/runnable; resumable `.suite/interview.json`; supports scripted answer sources for deterministic e2e; deferrals land in `open_questions`.
- **Scaffolder** — Spec → plugin.json + entry SKILL.md + playbooks derived from mutation policy + fixture stubs from triggers; GateRunner must be green before the result is shown.

## Phases (each ends with its own tests green + committed)

| Phase | Ships | Exit proof |
|---|---|---|
| 0 | Repo scaffold; stdlib unittest skeleton | repo exists, suite runs |
| 1 | Contracts + Reader + Profiler + GateRunner port + routing_contract | **Parity test**: new runner reproduces current script findings on Plugin-Template exactly |
| 2 | Snapshot/Delta engine + baseline store + `suite gates`/`diff` CLI | harness-baseline numbers reproducible through the new path |
| 3 | Extractor + Judge + `doctor` (read-only) | real doctor report on Plugin-Template incl. ≥1 judge advisory; zero mutations |
| 4 | Plan application + Transformer + 5 ops + rollback | padded scratch copy: approve `split_skill`, gates re-prove, Delta matches prediction; forced-failure rolls back cleanly |
| 5 | Interviewer + Scaffolder + `create` | idea → interview → scaffolded plugin passes validate; demo recorded in decisions/ |
| 6 | Dogfood + docs; feed decoupled-audit fix back to Plugin-Template | suite runs on itself; template benefits without bloat |

Effort shape: 1–2 mechanical, 3 medium, 4 is the heart, 5 small code / prompt-design heavy, 6 ongoing.

## Risks

- **Parity drift (Phase 1)** — guarded by the parity test; old scripts stay runnable until parity is proven.
- **Judge nondeterminism** — advisory-only, versioned rubric in Snapshot, never a gate.
- **Scope creep** — v1 hard stop at Agent Plugins 1.0.0; adapter profiles explicitly post-v1.
- **Template relationship** — suite consumes the template as first patient; backport only the decoupling fix, resist merging the suite into the template.
