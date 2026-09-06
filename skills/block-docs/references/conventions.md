# Block Documentation Conventions

Block documentation lets a reader re-derive a system change without re-reading the complete source. The structure is a form gate. The truth of a claim still requires reading primary source.

## Source pin and mode

One active campaign uses one source pin. Mixed pins decay because a citation can remain syntactically valid while describing a different system.

- In **code mode**, write `verified_against: <short-sha>`. Read source with `git show <pin>:<path>` or a worktree at that pin. First run `git status --short` in the source root and report uncommitted changes.
- In **spec mode**, write `verified_against: spec@<short-sha>`. Code may not exist. A cited symbol is planned and its absence is not `E006`.

A full refresh re-pins every active page only after the whole tree has been checked. Partial candidate pages stay outside the active tree until that review is complete. An add-block or incremental update retains the existing pin. If a new block needs newer code, the coordinator either schedules a full refresh or keeps a proposal outside the active tree. A writer never re-pins the whole tree alone.

## Citations and evidence

Cite a symbol, not a line number:

```text
src/worker.ts::retryTask()
src/config.ts::ConfigSchema
tests/worker.test.ts::"retryLimit"
```

A line number quickly points at unrelated code. In code mode, a `path::symbol` citation must find both path and symbol at the pin. In spec mode, a planned citation is skipped by `E006`, but the implementation plan must later create that named symbol.

Every claim-bearing sentence ends with one tag:

| Tag | Meaning |
|---|---|
| `[verified]` | Primary source was read or a measurement was run at the pin. |
| `[inferred]` | The claim follows from stated facts and the derivation is in the same sentence. |
| `[assumption]` | The claim came from memory or a secondary document without rechecking. |
| `[historical: <date>, <source>]` | The claim is a past measurement or event record that cannot be rerun. |
| `[design: §<N>]` | The claim comes from the named design section before implementation. |

Moving a claim from another page does not make it `[verified]`. Replace old measurements with a general description of citation decay unless the history itself changes a decision.

## Front matter and names

Every page begins with front matter using unquoted, single-line scalar values or flow-style lists with unquoted items. The linter's subset does not support YAML comments, quoted values, or multiline lists:

```yaml
---
block: <block-name>
doc: <UPPERCASE-KEBAB-NAME>
verified_against: <short-sha-or-spec@short-sha>
verified_on: <YYYY-MM-DD>
---
```

`doc:` equals the filename without `.md` and uses uppercase kebab form, for example `README`, `DATA-FLOW`, or `PERMISSIONS`. Additional pages are allowed. `block:` is the folder basename even for nested blocks. A file directly inside `docs-root` uses `block: _root`.

Only a block `README.md` has ownership fields:

```yaml
owns: [src/worker.ts, src/jobs/, src/plugins/**]
depends_on: [runtime/queue, storage]
```

`depends_on:` uses complete documentation identifiers relative to `docs-root`, such as `runtime/queue`, not the basename of a nested block.

## Ownership and fact placement

Every source file belongs to exactly one `owns:` list or to the explicit unassigned list in `OWNERSHIP.md` with a reason.

- `path/file.ts` names one file.
- `path/directory/` names a directory.
- `path/prefix/**` names a complete prefix.

Block ownership lists must be disjoint. Two entries overlap when they name the same file or when one directory or prefix contains the other. This prevents competing descriptions of one mechanism.

Nesting documentation does not grant overlapping source ownership. For example, a parent may own `src/runtime/bootstrap.ts` while its child owns `src/runtime/queue/`. The parent must not also claim `src/runtime/**`. A folder used only to group child folders is not a block; link its children from the root rather than inventing a parent owner.

Write mechanism details in the block that owns the enforcing code. A dependent block records only the consequence and links to the owner. Where ownership is disputed, the file owner keeps the mechanism.

## Contracts and enforcement

Each concrete contract under a leaf `##` or `###` heading in `CONTRACTS.md` has a nonempty `enforcement:` line. Group headings do not need a duplicate field. Wrap source citations in backticks, including citations in enforcement fields, so the linter can recognize them.

```text
enforcement: `src/config.ts::loadConfig()` (load time)
enforcement: `tests/worker.test.ts::retryLimit` (test suite)
enforcement: planned: `tests/worker.test.ts::retryLimit`
enforcement: convention
```

`planned:` is valid in spec mode. `convention` is an honest description of a real gap. Never invent a test or a mechanism to make enforcement look stronger.

## Required set and diagrams

Every block contains `README.md`, `CONTRACTS.md`, `INVARIANTS.md`, `GAPS.md`, and `OPERATIONS.md`. `DECISIONS.md` is optional. A parent with subblocks also has the full set.

`README.md` records the block boundary, ownership, dependencies, and one intra-block diagram. Root `DATA-FLOW.md` contains one system diagram. Use inline mermaid and do not repeat the same flow across pages.

- `CONTRACTS.md`: durable surfaces and their enforcement.
- `INVARIANTS.md`: behavior plus the defect, review, or risk that paid for it.
- `GAPS.md`: known debt, convention-only boundaries, and missed plans.
- `OPERATIONS.md`: starting, stopping, observability, and configuration or path resolvers.
- `DECISIONS.md`: decisions with the alternatives that lost.

Describe a resolver and its precedence, never only the result observed on one machine. When a system computes a value, cite its generator and the command that reproduces it instead of hand-copying a number.

## Style

Write plain, short, concrete prose. Do not copy private systems, domains, organizations, people, data, or historic numeric measurements into a reusable plugin. Do not use en dash or em dash. Use a comma, colon, full stop, or parentheses instead.

## Linter contract

Run:

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/blockdocs_lint.py" <docs-root> --repo <source-root> [--strict] [--no-git] [--exempt path]
```

`--no-git` deliberately checks current files rather than a git pin. `--exempt` takes a path relative to `docs-root`. Default exemptions are `reference`, `superpowers`, `comparisons`, `plans`, and `specs`.

| Code | Check |
|---|---|
| `E001` | Front matter is missing, unsupported, or lacks required fields. The accepted subset is scalars and flow-style lists. |
| `E002` | `block:` does not match its folder or a root page does not use `_root`. |
| `E003` | `doc:` does not match the filename or is not uppercase kebab. |
| `E004` | A block lacks one of the five required pages. |
| `E005` | Two `owns:` entries overlap as files, directories, or prefixes. |
| `E006` | A code-mode citation names a missing path or symbol at the pin. Spec-mode citations are skipped. Adding `planned:` to a code-mode page does not bypass this check. |
| `E007` | A pin is not an ancestor of `HEAD`. This check is skipped with `--no-git`. |
| `E008` | A concrete contract under a leaf `##` or `###` heading has no nonempty `enforcement:` field. |
| `W001` | More than one pin exists in the tree. |
| `W002` | Prose contains an en dash or em dash. |
| `W003` | A block page other than `README.md` has no evidence tag. |
| `E999` | No page was scanned. |

Errors exit with status `1`. Warnings exit with status `1` only under `--strict`. Usage errors exit with status `2`. The linter does not prove that a claim is true, complete, or semantically assigned to the right owner.
