# block-docs

A Claude Code plugin for creating and maintaining system documentation one building
block at a time. It packages a skill, a writer agent, a verifier agent, reusable
templates, and a structural linter.

The method divides a system by responsibility, states its contracts, separates
required behavior from known gaps, and anchors claims to a source revision. It also
supports writing documentation from a committed design spec before implementation
exists.

## What you get

- **Skill `block-docs`**: bootstrap documentation, add a block, refresh a tree, or
  audit ownership and evidence.
- **Agent `block-docs-writer`**: write or refresh one assigned block without editing
  application code or publishing changes.
- **Agent `block-docs-verifier`**: check a finished block section by section against
  the source pin and return a verdict, evidence, and proposed text for each section.
  It reads only; it never edits files.
- **Templates**: root navigation and the recurring pages for each block.
- **Linter**: check metadata, block structure, overlapping ownership, source
  citations, revision pins, and enforcement fields.

The goal is documentation detailed enough to inform a rewrite without treating
unverified assumptions as implemented behavior. This is not an API reference
compiler, a documentation website, or an autonomous background service.

## Install

In Claude Code:

```text
/plugin marketplace add kolezka/marketplace
/plugin install block-docs@kolezka
/reload-plugins
```

The marketplace is installed through Git. If access requires authentication, your
Git credentials must permit cloning the repository.

For local development, clone the repository and load the plugin without a persistent installation:

```sh
git clone https://github.com/kolezka/block-docs.git
claude --plugin-dir ./block-docs
```

The plugin ships no hooks, MCP servers, credentials, or permission overrides. The
writer and verifier inherit the session's model unless the coordinator picks another. Structural linting requires Python 3.9 or
newer and has no third-party runtime dependencies. Revision validation also needs
Git and the referenced commits in the local repository.

## Use

Create documentation from code:

```text
/block-docs:block-docs Document this repository under docs/. Read the source at HEAD,
identify its building blocks, and create the root pages and each block's page set.
```

Create documentation before implementation:

```text
/block-docs:block-docs Build docs/ from the committed design in specs/system.md.
Use spec@<commit>, design evidence tags, and planned enforcement. Do not invent code.
```

Maintain an existing tree:

```text
/block-docs:block-docs Refresh docs/ against HEAD. Check source changes, update the
affected blocks and cross-block links, and re-pin only after completing the review.
```

Audit without rewriting application code:

```text
/block-docs:block-docs Audit docs/ for stale citations, ownership overlap, missing
contracts, and claims that confuse conventions with enforcement. Report findings.
```

The skill coordinates the work. Its bundled agent handles one block at a time.
The coordinator supplies the source root, full docs root, block, owned paths,
source pin, evidence mode, and allowed output files. Spec mode also requires the
source-relative design path. Calling the agent directly requires that same brief.
Writing a block does not authorize re-pinning unrelated pages, changing source
code, committing, pushing, or deploying. These are agent instructions, not an
operating-system sandbox; harness permissions still apply.

Every block a writer produces goes to `block-docs-verifier` before it is accepted.
The verifier ignores the page's evidence tags, rereads the source at the pin, and
checks polarity, quantifiers over the whole source root, reachability, counts,
missing branches, writes from other blocks, and enforcement strength. Wrong or
partial sections get one fix round; what is still unresolved becomes a gap or goes
to the user. This costs one agent run per block. Use a different model for the
verifier than for the writer when one is available.

A partial edit does not justify updating every page's verification stamp. Additions
must fit the existing source pin or be treated as a separate proposal until the
full documentation campaign is refreshed.

## Documentation shape

```text
docs/
  README.md
  CONVENTIONS.md
  DATA-FLOW.md
  GLOSSARY.md
  OWNERSHIP.md
  block-name/
    README.md
    CONTRACTS.md
    INVARIANTS.md
    GAPS.md
    OPERATIONS.md
    DECISIONS.md       # optional
```

- **README** explains the block's boundary, owned files, dependencies, and flow.
- **CONTRACTS** records durable interfaces with an `enforcement:` field per entry.
- **INVARIANTS** records behavior that must survive, with its requirement or defect.
- **GAPS** records unknowns, missing enforcement, and debt rather than hiding them.
- **OPERATIONS** records schedules, path resolution, diagnostics, and recovery.
- **DECISIONS** records actual choices and rejected alternatives when available.

Contracts preserve shape. Invariants preserve behavior. Gaps are not obligations to
reproduce defects. A fact belongs to the block owning its mechanism; other blocks
link to it instead of copying it.

Code-derived pages use a commit pin and evidence tags such as `[verified]`,
`[inferred]`, `[assumption]`, and `[historical: date, source]`. The first three also
accept detail after a colon, such as `[verified: src/app.ts::start()]`. A claim that
uses an absolute word, such as every, only, never, or read-only, carries a `scope:` line naming
the command that enumerated the set. Spec-derived pages use
`spec@<commit>`, `[design: §N]`, and `enforcement: planned: ...`. A plan is not proof
that a test or implementation exists.

See the [full conventions](skills/block-docs/references/conventions.md),
[orchestration guide](skills/block-docs/references/orchestration.md), and
[templates](skills/block-docs/references/templates/).

## Run the linter

Use the script from a checkout of this repository. Pass the complete documentation
root, even when you changed only one block:

```sh
python3 /path/to/block-docs/scripts/blockdocs_lint.py \
  /path/to/project/docs --repo /path/to/project
```

Treat warnings as failures:

```sh
python3 scripts/blockdocs_lint.py /path/to/project/docs \
  --repo /path/to/project --strict
```

By default, citations are checked against each page's source pin, not whatever is
currently in the working tree. To intentionally check working files without Git
revision validation:

```sh
python3 scripts/blockdocs_lint.py /path/to/project/docs \
  --repo /path/to/project --no-git
```

Check for drift between each page's pin and a newer commit:

```sh
python3 scripts/blockdocs_lint.py /path/to/project/docs \
  --repo /path/to/project --drift HEAD
```

`--drift` reports cited files that changed after the pin and reverts that touched a
block's owned paths. The ref must resolve, and `--drift` cannot be combined with
`--no-git`. When the ref is not a descendant of a page's pin, that page's drift
checks are skipped with a note line, not a finding.

The documentation directory must resolve inside `--repo`. Source and documentation
paths that escape this root are rejected.

The default exemptions are `reference/`, `superpowers/`, `comparisons/`, `plans/`,
and `specs/`, relative to the documentation root. Add a narrowly scoped exemption
for carried-forward material that does not use this format:

```sh
python3 scripts/blockdocs_lint.py /path/to/project/docs \
  --repo /path/to/project --exempt archived-guides
```

Exemptions are skipped entirely. Do not exempt active block pages merely to hide
findings. The linter reads documentation files on disk, including untracked pages.
Checks in the target project that enumerate only tracked files may have a different
scope.

| Code | Level | Checks |
|---|---|---|
| E001 | Error | Supported front matter, required fields, and field values |
| E002 | Error | Block name matches its folder; root pages use `_root` |
| E003 | Error | Page name matches the file stem |
| E004 | Error | Required block pages exist |
| E005 | Error | Ownership entries overlap between different blocks |
| E006 | Error | Recognized code-mode citations, including colon-tag detail citations, resolve at their source pin |
| E007 | Error | Source pin exists and is an ancestor of `HEAD` |
| E008 | Error | Concrete contract entries have nonempty enforcement fields |
| W001 | Warning | The tree mixes source pins |
| W002 | Warning | Prose contains an en dash or em dash |
| W003 | Warning | A non-README block page has no recognized evidence tag, plain or colon form |
| W004 | Warning | A `[verified]` contract or invariant claim uses an absolute word and its section, or the intro text it sits in, has no `scope:` line naming a command in backticks or a path set with `/` |
| W005 | Warning | A `[verified]` paragraph or list item on a non-README block page has no recognized citation, unless its leaf section has a `scope:` line naming a command or path set |
| W006 | Warning | With `--drift REF`: a cited source file changed between the page pin and REF |
| W007 | Warning | With `--drift REF`: a commit in pin..REF whose subject starts with `revert` (any case, merge reverts included) touches the block's owned paths |
| E999 | Error | No non-exempt documentation was scanned |

Exit status is `0` for no blocking findings, `1` for findings, and `2` for invalid
usage, including `--drift` with `--no-git` or a ref that does not resolve. Warnings
block only with `--strict`. `W004` through `W007` apply to code-mode pages.

### What a clean result does not prove

The linter is a structural check, not a documentation judge. Lint clean does not
mean the claims are true; verifier verdicts are the claim gate. It does not prove
that:

- each factual sentence has an accurate evidence tag;
- a claim tagged `[verified]` was checked, or that its citation supports it;
- a `scope:` line covers the whole set the claim quantifies over;
- a predicate is described with the right polarity, or a cited mechanism is reachable;
- a named test actually runs or enforces the described contract;
- every tracked file has an owner;
- descriptions, links, and diagrams are semantically correct;
- private names or secrets have been removed;
- planned source paths exist in a spec-only project;
- a page is current: without `--drift`, changes after the pin are not examined.

Citation checks are fixed-text checks of recognized inline `path::symbol` forms,
not language-aware symbol resolution. Fenced examples are excluded. Spec-mode
planned citations are not checked as existing implementation. Front matter uses a
small supported subset of YAML: unquoted, single-line scalar fields and flow-style
lists with unquoted items. Quoted YAML values, multiline lists, and comments are
not supported. Normalize them before linting. With `--no-git`, pin comparison uses
literal metadata strings because commit identity cannot be resolved.

## Development

Run the test suite from this checkout:

```sh
env -u FORCE_COLOR uv run pytest -q
```

Validate both manifests with the installed Claude Code CLI:

```sh
claude plugin validate .claude-plugin/plugin.json --strict
claude plugin validate .claude-plugin/marketplace.json --strict
```

A manifest-only pass does not prove component discovery. After installing the
plugin, inspect the actual skill and agent inventory:

```sh
claude plugin details block-docs@kolezka
```

The tests use isolated fixture repositories. Mutation checks and practical skill
scenarios are separate checks; a passing unit suite alone does not demonstrate the
writer's behavior.

[`evals/`](evals/README.md) holds behavioral scenarios for the writer and the
verifier. Each one is a small source tree with a documented block that contains one
planted wrong section and the verdict a verifier should return. They are run by
hand with agents, not by pytest; the test suite checks only their structure.

Official installation and path contracts:
[marketplaces](https://code.claude.com/docs/en/plugin-marketplaces),
[plugin reference](https://code.claude.com/docs/en/plugins-reference), and
[skills](https://code.claude.com/docs/en/skills).
