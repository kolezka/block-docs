---
block: catalog
doc: INVARIANTS
verified_against: PIN
verified_on: 2026-01-15
---

# Invariants

## 1. Prices table is read-only at runtime

The `prices` table is read-only at runtime: no code path writes it, and the application only reads it through `src/catalog/prices.ts::getPrice()` and `src/catalog/prices.ts::listPrices()`. Prices change only through data loads outside the application. [verified]

scope: `git grep -n "prices" <pin> -- src/catalog/`

## 2. Lookup matches both SKU and currency

`src/catalog/prices.ts::getPrice()` filters by both `sku` and `currency` and returns the first row or null; see [Uniqueness is not enforced here](GAPS.md). [verified: src/catalog/prices.ts::"WHERE sku = $1 AND currency = $2"]
