---
name: beta
description: Tracks incidents and operational corrections.
---

# Beta

Beta maintains the incident log and tracks operational corrections.

Every incident gets one dated line with severity and a short cause.

Severity uses minor, major, or critical, in that order of impact.

Corrections are appended; earlier entries are never edited.

A correction must reference the incident it resolves by date.

Weekly, review open incidents and close resolved ones.

If two incidents share a root cause, note the link on both lines.

Keep causes concrete: name the subsystem and the observable effect.

Compare notes with [Alpha](../alpha/SKILL.md) when sources disagree.
