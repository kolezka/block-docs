---
block: search
doc: CONTRACTS
verified_against: PIN
verified_on: 2026-01-15
---

# Contracts

## Search route

`src/search/routes.ts::handleSearch()` reads the query from `params.q`, treats a missing value as an empty query, and returns status 200 with the results of `src/search/service.ts::search()`. [verified: src/search/routes.ts::"params.q ??"]

enforcement: `src/search/routes.ts::handleSearch()` (call time)

## Result limit

`src/search/service.ts::search()` returns at most `limit` results, defaulting to `src/search/service.ts::DEFAULT_LIMIT`, which is 20. [verified: src/search/service.ts::"DEFAULT_LIMIT = 20"]

enforcement: `src/search/service.ts::search()` (call time)
