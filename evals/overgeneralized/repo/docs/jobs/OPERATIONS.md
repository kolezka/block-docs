---
block: jobs
doc: OPERATIONS
verified_against: PIN
verified_on: 2026-01-15
---

# Operations

## Start and stop

The queue starts empty when `src/jobs/queue.py` is imported and has no stop action. [verified: src/jobs/queue.py::"_jobs = {}"]

## Observe

The block has no logging or metrics; the job dictionary is the only state to inspect. [verified: src/jobs/queue.py::_jobs]

## Configuration and paths

The retry limit is the source constant `src/jobs/queue.py::MAX_ATTEMPTS` with no runtime override. [verified]

## Failure and recovery

A restart drops all queued jobs; see the in-memory gap in [GAPS](GAPS.md). [inferred: from the module-level dictionaries]
