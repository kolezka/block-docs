---
block: entitlements
doc: GAPS
verified_against: PIN
verified_on: 2026-01-15
---

# Gaps

## No test for the access predicate

No test file exists in this source tree, so the tier behavior of `src/entitlements/access.ts::hasPremiumAccess()` has no automated check. [verified]

scope: `git ls-tree -r --name-only <pin>` (no test files listed)
