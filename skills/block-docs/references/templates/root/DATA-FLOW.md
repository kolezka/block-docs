---
block: _root
doc: DATA-FLOW
verified_against: <short-sha-or-spec@short-sha>
verified_on: <YYYY-MM-DD>
---

# System data flow

<!-- Summarize the complete system flow in tagged sentences before the diagram. -->

## Whole-system flow

<!-- Keep one mermaid diagram here and link to block READMEs for internal detail. -->

```mermaid
flowchart TD
    A["<input>"] --> B["<block or boundary>"]
    B --> C["<output>"]
```

## Ownership of hops

<!-- Name the block that owns each meaningful hop and link to its documentation. -->

| Hop | Owning block | Evidence |
|---|---|---|
| `<source> to <destination>` | [`<block>`](<docs-relative-id>/README.md) | `[<evidence-tag>]` |
