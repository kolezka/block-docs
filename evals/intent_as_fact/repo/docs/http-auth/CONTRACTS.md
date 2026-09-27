---
block: http-auth
doc: CONTRACTS
verified_against: PIN
verified_on: 2026-01-15
---

# Contracts

## Session cookie name

The session is read from the cookie named `sid`, set by `src/middleware/session.ts::SESSION_COOKIE`. [verified: src/middleware/session.ts::SESSION_COOKIE]

enforcement: `src/middleware/session.ts::SESSION_COOKIE` (constant)

## Session validation

`src/middleware/session.ts::requireSession()` validates the session before a protected handler runs: it rejects a missing, unknown, or expired session with status 401, and passes a valid session on as `req.sessionToken`. [verified: src/middleware/session.ts::"Validates the session before any protected handler runs."]

enforcement: `src/middleware/session.ts::requireSession()` (every protected route)
