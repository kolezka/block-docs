---
name: block-docs
description: Use when creating, extending, refreshing, or auditing block-style system documentation, especially when requests mention CONTRACTS, INVARIANTS, GAPS, evidence tags, source pins, or enforcement fields.
---

# Block Documentation

Create documentation from which a reader can re-derive a system change without re-reading the whole codebase. Each page describes one ownership boundary and states both its source and its evidence level.

## When to use

Use for a system documentation tree that records contracts, invariants, gaps, operations, and ownership boundaries.

Do not use for a single `README.md`, an API reference, a deployment guide, or a tutorial without a block decomposition.

## Load this plugin's resources

When this skill is loaded by the plugin, read its resources through the interpolated plugin root:

- `${CLAUDE_PLUGIN_ROOT}/skills/block-docs/references/conventions.md`: rules, front matter, and linter behavior.
- `${CLAUDE_PLUGIN_ROOT}/skills/block-docs/references/orchestration.md`: multi-block campaigns, writer scope, and handoff.
- `${CLAUDE_PLUGIN_ROOT}/skills/block-docs/references/templates/root/`: pages directly under the docs root.
- `${CLAUDE_PLUGIN_ROOT}/skills/block-docs/references/templates/block/`: the complete file set for one block.

Do not assume `~`, an installed copy of another repository, or another skill. When files are read outside the plugin loader, use the absolute `plugin_root` supplied by the coordinator instead of deriving one.

## Tree shape

```text
docs/
  README.md
  CONVENTIONS.md
  GLOSSARY.md
  DATA-FLOW.md
  OWNERSHIP.md
  <block>/
    README.md
    CONTRACTS.md
    INVARIANTS.md
    GAPS.md
    OPERATIONS.md
    DECISIONS.md          # optional
```

Every block, including a parent that has subblocks, has the five required pages. A parent `README.md` may navigate the hierarchy but does not replace its contracts or boundary. Additional pages, such as `PERMISSIONS.md`, are valid when their filename and `doc:` value agree.

Two modes use the same rules:

- **code mode**: `verified_against: <short-sha>`, with claims read from code at that pin.
- **spec mode**: `verified_against: spec@<short-sha>`, with claims read from a design before code exists.

## Short rules

1. Keep one source pin for one active tree and one campaign.
2. Cite `path::function()`, `path::TypeOrConstant`, or `path::"quoted phrase"` in backticks, never by line number.
3. End every claim-bearing sentence with an evidence tag.
4. Put front matter on every page. `block` is the folder basename and root pages use `_root`.
5. Keep mechanism details in the block that owns the enforcing code. Dependent blocks state the consequence and link back.
6. Add a nonempty `enforcement:` field to every contract entry.
7. Keep `owns:` disjoint across blocks and record deliberately unassigned paths.
8. Describe a resolver and its precedence, not a machine-specific result.
9. Put one system diagram in `DATA-FLOW.md` and one intra-block diagram in each block `README.md`.
10. Tag `[verified]` only for a check run on this claim at the pin. Back every absolute word with a `scope:` line and quote predicates. See "Claim discipline" in `references/conventions.md`.

## Verify every block

Lint clean does not mean the claims are true. The claim gate is the `block-docs-verifier` agent, which checks each section of a finished block against the pin and returns a verdict per section. Every workflow below that writes a block runs this loop before lint:

1. The writer finishes the block.
2. Dispatch `block-docs-verifier` for that block with `docs_root`, `source_root`, `pin`, `block_id`, `owned_paths`, and `pages` (default `CONTRACTS.md`, `INVARIANTS.md`, `GAPS.md`). Run it on a different model than the writer when one is available.
3. Send `wrong` and `partial` sections, with the verifier's evidence and proposed text, back to the writer for one fix round.
4. Re-verify the fixed sections. Rewrite any section still unresolved as a gap in `GAPS.md`, or report it to the user. Do not loop further.
5. List suspected code bugs from the verifier for the user. Do not fix code in a docs campaign.

For a block with many sections, dispatch the verifier once per page instead of once per block, and read its "Scope not checked" list before accepting. The verifier costs one agent run per block (or per page), plus a short re-check after the fix round. Budget for it; the step is not optional.

Read `references/conventions.md` for the full rules and their reasons.

## Workflow: bootstrap

1. Establish `docs-root`, `source-root`, mode, and one source pin. Run `git status --short` in `source-root` to expose uncommitted changes.
2. In code mode, read the source only with `git show <pin>:<path>`, `git grep <pattern> <pin>`, `git ls-tree <pin>`, or a read-only worktree at that pin. `rg` over the working tree only locates files; it is not evidence. In spec mode, identify the source-relative `spec_path` and read `git show <sha>:<spec_path>`, stripping `spec@` only for Git commands.
3. Fill the root templates, then the complete template set for every block.
4. Tag every claim and verify each citation at the source pin.
5. Run the verify loop above for every block.
6. Run the linter against the full `docs-root`. When a linter check is new, add its test and kill that check with one mutation in a disposable copy.

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/blockdocs_lint.py" <docs-root> --repo <source-root> [--strict] [--no-git | --drift <ref>] [--exempt path]
```

## Workflow: add-block or incremental update

1. Keep the existing pin and verify the new scope at that pin.
2. Add the full block set, its ownership, and its dependencies.
3. Do not rewrite other pins without verification.
4. If the new block needs newer code, ask the coordinator for a full refresh or keep a proposal outside the active tree.
5. Run the verify loop above for the new or changed block.
6. Finish with the full-root lint command above and run the relevant test for any new linter check.

## Workflow: refresh and re-pin

1. Let the coordinator choose a new pin and one campaign scope.
2. Read each source only at that pin, never from the current working tree.
3. A completed refresh covers every active page. If the campaign stops early, keep the candidate pages outside the active tree and report the unfinished scope. Do not leave mixed pins as a completed refresh.
4. Do not re-pin the whole tree because one block needs newer source.
5. Run the verify loop above for every refreshed block at the new pin.
6. Finish with the full-root lint command above and mutate each new linter check once.

## Workflow: audit coverage

1. Compare `owns:` with the source tree and record every intentionally unassigned path with a reason.
2. Check citations at the pin, evidence tags, `enforcement:`, and dependency identifiers.
3. Record a real enforcement gap as `convention`, never as an invented test or mechanism.
4. Finish with the full-root lint command above, adding `--strict` when warnings are intended to gate the tree.

A semantic audit also checks whether claims are true:

1. Run the linter with `--drift <new-HEAD>` to list cited files that changed since the pin and reverts that touched each block.
2. Dispatch `block-docs-verifier` once per block with `compare_ref: <new-HEAD>`, so claims that changed after the pin come back as `stale`.
3. Report verdict counts per block, the wrong and stale sections with proposed text, and suspected code bugs. An audit reports; it does not rewrite pages unless the user asks.

## Orchestration and lint

For many blocks, read `references/orchestration.md` before assigning writers and verifiers. A writer gets a small, verifiable scope. The coordinator selects the campaign and resolves ownership conflicts.

The linter checks structure, not the truth of claims. Verifier verdicts are the claim gate. The linter skips carried-forward material in `reference`, `superpowers`, `comparisons`, `plans`, and `specs` by default. Use `--exempt <path>` only for intentionally carried-forward material, with a path relative to `docs-root`. It exits `0` when clean, `1` for errors or strict warnings, and `2` for usage errors. `references/conventions.md` defines `E001` through `E008`, `W001` through `W007`, and `E999`. `W006` and `W007` run only with `--drift <ref>`, which cannot be combined with `--no-git`.
