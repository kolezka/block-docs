---
block: search
doc: OPERATIONS
verified_against: PIN
verified_on: 2026-01-15
---

# Operations

## Start and stop

The block has no process of its own; `src/search/routes.ts::handleSearch()` runs inside whatever server imports it. [inferred: the source tree has no entry point]

## Observe

The route logs nothing, and its one return statement uses status 200. [verified: src/search/routes.ts::"status: 200"]

## Configuration and paths

The default result limit is the source constant `src/search/service.ts::DEFAULT_LIMIT`, with no runtime override. [verified]

## Failure and recovery

The index is passed in by the caller, so a stale result reflects a stale index outside this block. [inferred: `search()` takes the index as an argument]
