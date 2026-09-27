---
block: entitlements
doc: OPERATIONS
verified_against: PIN
verified_on: 2026-01-15
---

# Operations

## Start and stop

The block has no process of its own; `src/entitlements/routes.ts::exportReport()` runs inside whatever server imports it. [inferred: the source tree has no entry point]

## Observe

The route logs nothing; the 403 body `premium_required` is the only signal of a denied export. [verified: src/entitlements/routes.ts::"premium_required"]

## Configuration and paths

The unpaid tier set is a constant in source, `src/entitlements/tiers.ts::UNPAID_TIERS`, with no runtime override. [verified]

## Failure and recovery

A wrong tier on an account changes access immediately; the fix is to correct the account record. [inferred: the predicate reads the tier on every call]
