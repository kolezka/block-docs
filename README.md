# block-docs

A Claude Code plugin for creating and maintaining system documentation one building
block at a time. It packages a skill, a writer agent, reusable templates, and a
structural linter.

The method divides a system by responsibility, states its contracts, separates
required behavior from known gaps, and anchors claims to a source revision. It also
supports writing documentation from a committed design spec before implementation
exists.

## What you get

- **Skill `block-docs`**: bootstrap documentation, add a block, refresh a tree, or
  audit ownership and evidence.
- **Agent `block-docs-writer`**: write or refresh one assigned block without editing
  application code or publishing changes.
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
writer inherits the session's model. Structural linting requires Python 3.9 or
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
`[inferred]`, `[assumption]`, and `[historical: date, source]`. Spec-derived pages use
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
| E006 | Error | Recognized code-mode citations resolve at their source pin |
| E007 | Error | Source pin exists and is an ancestor of `HEAD` |
| E008 | Error | Concrete contract entries have nonempty enforcement fields |
| W001 | Warning | The tree mixes source pins |
| W002 | Warning | Prose contains an en dash or em dash |
| W003 | Warning | A non-README block page has no recognized evidence tag |
| E999 | Error | No non-exempt documentation was scanned |

Exit status is `0` for no blocking findings, `1` for findings, and `2` for invalid
usage. Warnings block only with `--strict`.

### What a clean result does not prove

The linter is a structural check, not a documentation judge. It does not prove
that:

- each factual sentence has an accurate evidence tag;
- a named test actually runs or enforces the described contract;
- every tracked file has an owner;
- descriptions, links, and diagrams are semantically correct;
- private names or secrets have been removed;
- planned source paths exist in a spec-only project.

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

Official installation and path contracts:
[marketplaces](https://code.claude.com/docs/en/plugin-marketplaces),
[plugin reference](https://code.claude.com/docs/en/plugins-reference), and
[skills](https://code.claude.com/docs/en/skills).
