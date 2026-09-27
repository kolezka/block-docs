---
block: jobs
doc: CONTRACTS
verified_against: PIN
verified_on: 2026-01-15
---

# Contracts

## Enqueue signature

`src/jobs/queue.py::enqueue()` takes a job name, a payload, and an optional `dedupe_key`, and returns a job id string. [verified]

enforcement: `src/jobs/queue.py::enqueue()` (call time)

## Deduplication by key

When `dedupe_key` is set and already indexed, `src/jobs/queue.py::enqueue()` returns the first job id and adds no job, as the check `src/jobs/queue.py::"dedupe_key in _dedupe_index"` shows. A call without a key always adds a new job. [verified]

scope: `git grep -n "_dedupe_index" <pin> -- src/` (one read and one write, both in enqueue)

enforcement: `src/jobs/queue.py::enqueue()` (call time)
