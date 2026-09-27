---
block: http-auth
doc: INVARIANTS
verified_against: PIN
verified_on: 2026-01-15
---

# Invariants

## 1. Rejection stops the chain

When `src/middleware/session.ts::requireSession()` answers 401 it returns without calling `next`, so no later handler runs for that request. [verified: src/middleware/session.ts::"res.status(401).end();"]

## 2. Account routes are guarded

Both account routes list `requireSession` as a handler in `src/account/routes.ts::accountRoutes`. [verified]

scope: `git grep -n "path:" <pin> -- src/account/` (two routes, both list requireSession)
