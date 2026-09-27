---
block: search
doc: INVARIANTS
verified_against: PIN
verified_on: 2026-01-15
---

# Invariants

## 1. Hidden items never appear in results

Search results never include an item whose `hidden` flag is set: `src/search/filters.ts::excludeHidden()` drops them with `src/search/filters.ts::"!item.hidden"` before the limit is applied. [verified]

scope: `git grep -n "hidden" <pin> -- src/search/filters.ts`

## 2. Blank queries return nothing

A query that is empty after trimming returns an empty list rather than the whole index, through the check `src/search/service.ts::"needle.length === 0"`. [verified: src/search/service.ts::search()]

## 3. Results are ordered by score

`src/search/service.ts::rankResults()` sorts matches by descending `score` before the limit is applied, so the limit keeps the best matches. [verified: src/search/service.ts::"b.score - a.score"]
