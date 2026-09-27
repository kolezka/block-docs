---
block: jobs
doc: INVARIANTS
verified_against: PIN
verified_on: 2026-01-15
---

# Invariants

## 1. Producers are idempotent

Every producer passes a stable `dedupe_key` to `src/jobs/queue.py::enqueue()`, derived from the business id it enqueues, as in `src/jobs/producers/invoice.py::"format(invoice_id)"`. A retried request therefore never adds a second job. [verified]

scope: `git grep -n "dedupe_key=" <pin> -- src/jobs/producers/invoice.py`
