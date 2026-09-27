---
block: <block-name>
doc: INVARIANTS
verified_against: <short-sha-or-spec@short-sha>
verified_on: <YYYY-MM-DD>
---

# Invariants

<!-- Record behavior that a rewrite must preserve, plus the defect, review, or risk that paid for it. If the code violates an invariant at the pin, it is not an invariant: move it to GAPS.md, link it from here, and report a suspected code bug. -->

## 1. <Invariant name>

<!-- State the behavior, its source, and the failure it prevents in tagged sentences. -->

<invariant claim> [<evidence-tag>]

<!-- Required when a claim uses every, only, never, always, all, none, cannot, read-only, or no other; optional otherwise. The value must be a command in backticks, such as `git grep -n "<pattern>" <pin> -- .`, or a path set containing `/`. -->
scope: `<command run at the pin>` or <path/set/>

## 2. <Invariant name>

<!-- State the next independent behavior and why it must remain true. -->

<invariant claim> [<evidence-tag>]

<!-- Required when a claim uses every, only, never, always, all, none, cannot, read-only, or no other; optional otherwise. The value must be a command in backticks, such as `git grep -n "<pattern>" <pin> -- .`, or a path set containing `/`. -->
scope: `<command run at the pin>` or <path/set/>
