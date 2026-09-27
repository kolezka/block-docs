---
block: jobs
doc: GAPS
verified_against: PIN
verified_on: 2026-01-15
---

# Gaps

## Retry limit has no caller

`src/jobs/queue.py::record_failure()` is defined but nothing in the source tree calls it, so the retry limit is not applied by any live path. [verified]

scope: `git grep -n "record_failure" <pin> -- src/` (one definition, no call)

## Queue state is in memory

Jobs and the deduplication index live in module dictionaries, `src/jobs/queue.py::_jobs` and `src/jobs/queue.py::_dedupe_index`, so a restart loses both. [verified]
