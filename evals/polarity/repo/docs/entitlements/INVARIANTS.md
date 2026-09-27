---
block: entitlements
doc: INVARIANTS
verified_against: PIN
verified_on: 2026-01-15
---

# Invariants

## 1. Suspension overrides tier

A suspended account is denied premium access whatever its tier, because `src/entitlements/access.ts::hasPremiumAccess()` returns false on `account.suspended` before it reads the tier. [verified]

scope: `git grep -n "suspended" <pin> -- src/` (the type field and the one check in access.ts)

This prevents a suspended account from exporting reports through a paid tier. [inferred: from the check order above]
