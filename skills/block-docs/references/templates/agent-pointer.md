<!-- block-docs:start -->
## System documentation (block-docs)

This repository has block documentation in `<docs-root>/`. Use it before you change code or answer a question about how the system works. It is faster than re-reading the source and it records rules the code does not show.

- Start at `<docs-root>/README.md` for the block map. `<docs-root>/OWNERSHIP.md` maps source paths to blocks.
- Before you edit a file, find the block whose `owns:` list (front matter of `<docs-root>/<block>/README.md`) covers it. Read that block's `CONTRACTS.md` and `INVARIANTS.md`, and `GAPS.md` for known debt.
- Keep every documented contract and invariant unless the task is to change it. If your change breaks one, say so and name the page that is now stale.
- Rules in `GAPS.md` or with `enforcement: convention` are not enforced by code. Do not assume a check will catch you.
- Pages describe the code at the commit in their `verified_against:` field. For a file changed since then, run `git diff <pin> -- <path>`; when the page and the code disagree, the code wins and the page is stale.
- `[verified]` means checked at the pin. `[inferred]` and `[assumption]` are weaker; confirm them in code before you rely on them.
<!-- block-docs:end -->
