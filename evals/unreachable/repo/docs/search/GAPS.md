---
block: search
doc: GAPS
verified_against: PIN
verified_on: 2026-01-15
---

# Gaps

## Substring matching only

Matching is a case-insensitive substring test on `title`, `src/search/service.ts::"item.title.toLowerCase().includes(needle)"`, with no tokenizing or field weighting. [verified]

## No tests

The source tree has no test files, so none of the contracts above has an automated check. [verified]

scope: `git ls-tree -r --name-only <pin>` (no test files listed)
