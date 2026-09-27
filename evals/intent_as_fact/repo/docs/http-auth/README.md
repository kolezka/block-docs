---
block: http-auth
doc: README
verified_against: PIN
verified_on: 2026-01-15
owns: [src/middleware/]
depends_on: []
---

# HTTP auth middleware

This block provides the request middleware that guards protected routes with a session cookie. [verified: src/middleware/session.ts::requireSession()]

## Boundary

The block owns the middleware and its request types. The routes that mount it live in `src/account/`, which has no block page in this tree. [verified: src/account/routes.ts::accountRoutes]

## Owned sources

| Source | Role | Evidence |
|---|---|---|
| `src/middleware/session.ts` | Session middleware and cookie name | `[verified]` |
| `src/middleware/types.ts` | Request, response, and next types | `[verified]` |

## Dependencies

This block has no documented dependencies. [verified: src/middleware/session.ts::"./types"]

## Intra-block flow

```mermaid
flowchart TD
    A["request"] --> B["requireSession()"]
    B -->|no cookie| C["401"]
    B -->|cookie| D["next handler"]
```
