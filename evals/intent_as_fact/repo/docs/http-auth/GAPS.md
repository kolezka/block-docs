---
block: http-auth
doc: GAPS
verified_against: PIN
verified_on: 2026-01-15
---

# Gaps

## No tests

The source tree has no test files, so the middleware has no automated check. [verified]

scope: `git ls-tree -r --name-only <pin>` (no test files listed)

## Route mounting is by hand

A new protected route is guarded only if its author adds `requireSession` to its handler list in `src/account/routes.ts::accountRoutes`; nothing checks that. [verified]

scope: `git grep -n "requireSession" <pin> -- src/` (defined in session.ts, listed only in accountRoutes)

enforcement: convention
