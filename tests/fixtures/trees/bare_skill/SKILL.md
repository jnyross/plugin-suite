---
name: bare-skill
description: Answers questions about retry logic.
---

# Retry Backoff

This skill explains how retry backoff behaves when a remote call fails.

Retries are attempted with exponential delay between attempts.

The first retry waits one second before the request is reissued.

Each subsequent attempt doubles the previous wait duration.

A jitter factor is applied so concurrent clients do not align.

After five failed attempts the client gives up and surfaces the error.

Transient network faults are the expected trigger for retries.

Permanent HTTP status codes are never retried by this logic.

Callers can inspect the last failure to decide on manual follow-up.

Backoff state resets whenever a request finally succeeds.

See [Guide](references/guide.md) for worked examples of each stage.
