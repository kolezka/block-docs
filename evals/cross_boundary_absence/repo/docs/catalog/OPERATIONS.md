---
block: catalog
doc: OPERATIONS
verified_against: PIN
verified_on: 2026-01-15
---

# Operations

## Start and stop

The block has no process of its own; `src/catalog/routes.ts::handleGetPrice()` runs inside whatever server imports it. [inferred: the source tree has no entry point]

## Observe

The route logs nothing; a 404 with `price_not_found` is the signal of a missing price. [verified: src/catalog/routes.ts::"price_not_found"]

## Configuration and paths

The database connection is passed in as a `Db` argument, so this block resolves no connection settings itself. [verified: src/catalog/prices.ts::"db: Db"]

## Failure and recovery

A missing price row yields 404 until a row for that SKU and currency exists. [inferred: from the lookup route contract]
