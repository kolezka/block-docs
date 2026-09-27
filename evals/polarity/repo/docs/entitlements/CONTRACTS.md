---
block: entitlements
doc: CONTRACTS
verified_against: PIN
verified_on: 2026-01-15
---

# Contracts

## Tier values

An account tier is one of `free`, `trial`, `basic`, `pro`, or `grace`, as declared by `src/entitlements/tiers.ts::Tier`. [verified]

enforcement: `src/entitlements/tiers.ts::Tier` (type check)

## Premium access check

`src/entitlements/access.ts::hasPremiumAccess()` returns true for the paid tiers `basic` and `pro`, and excludes `trial` and `grace` accounts along with `free`. [verified: src/entitlements/tiers.ts::"Trial and grace accounts are not paid tiers."]

enforcement: `src/entitlements/access.ts::hasPremiumAccess()` (call time)

## Report export response

`src/entitlements/routes.ts::exportReport()` returns status 403 with body `premium_required` when the access check fails, and status 200 with the report otherwise. [verified: src/entitlements/routes.ts::"premium_required"]

enforcement: `src/entitlements/routes.ts::exportReport()` (call time)
