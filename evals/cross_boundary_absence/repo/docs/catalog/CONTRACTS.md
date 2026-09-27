---
block: catalog
doc: CONTRACTS
verified_against: PIN
verified_on: 2026-01-15
---

# Contracts

## Price shape

A price has `sku`, `currency`, and `amountCents`, with the column `amount_cents` renamed in each query. [verified: src/catalog/prices.ts::"amount_cents AS amountCents"]

enforcement: `src/catalog/prices.ts::Price` (type check)

## Price lookup route

`src/catalog/routes.ts::handleGetPrice()` returns status 404 with error `price_not_found` when no row matches the SKU and currency, and status 200 with the price otherwise. [verified: src/catalog/routes.ts::"price_not_found"]

enforcement: `src/catalog/routes.ts::handleGetPrice()` (call time)
