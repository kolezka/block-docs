---
block: <block-name>
doc: CONTRACTS
verified_against: <short-sha-or-spec@short-sha>
verified_on: <YYYY-MM-DD>
---

# Contracts

<!-- Record durable entry points, schemas, formats, or configuration surfaces. -->

## <Contract name>

<!-- State the contract, cite its source symbol, and end each claim with an evidence tag. -->

<contract claim> [<evidence-tag>]

<!-- Required when a claim uses every, only, never, always, all, none, cannot, read-only, or no other; optional otherwise. The value must be a command in backticks, such as `git grep -n "<pattern>" <pin> -- .`, or a path set containing `/`. -->
scope: `<command run at the pin>` or <path/set/>

enforcement: <citation with strength, planned: symbol, or convention>

## <Another contract name>

<!-- State the next independent contract and its evidence. -->

<contract claim> [<evidence-tag>]

<!-- Required when a claim uses every, only, never, always, all, none, cannot, read-only, or no other; optional otherwise. The value must be a command in backticks, such as `git grep -n "<pattern>" <pin> -- .`, or a path set containing `/`. -->
scope: `<command run at the pin>` or <path/set/>

enforcement: <citation with strength, planned: symbol, or convention>
