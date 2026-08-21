# Retry Guide

Worked examples for each backoff stage.

1. Initial call fails with a timeout; schedule a retry in 1s.
2. Second failure doubles the window to 2s plus jitter.
3. Third failure yields 4s, fourth 8s, fifth 16s.
4. After the fifth failure, stop and report the error upstream.

Keep total retry wall time under thirty seconds for interactive calls.
