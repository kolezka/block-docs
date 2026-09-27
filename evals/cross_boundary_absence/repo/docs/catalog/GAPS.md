---
block: catalog
doc: GAPS
verified_against: PIN
verified_on: 2026-01-15
---

# Gaps

## Uniqueness is not enforced here

`src/catalog/prices.ts::getPrice()` takes the first row when several match, and this source tree has no schema that makes SKU and currency unique. [verified: src/catalog/prices.ts::"rows.length > 0 ? rows[0] : null"]

scope: `git ls-tree -r --name-only <pin>` (no schema or migration files)

## listPrices has no caller

`src/catalog/prices.ts::listPrices()` is exported but not called anywhere in the source tree. [verified]

scope: `git grep -n "listPrices" <pin> -- src/` (one definition, no call)
