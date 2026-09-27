# Behavioral evals

These scenarios check how `block-docs-writer` and `block-docs-verifier` behave on small, invented source trees. Each tree has one trap of a kind that often produces a wrong claim. They are run by hand with agents, not by pytest. `tests/test_package.py` checks only that each scenario is well formed.

## Layout

```text
evals/<scenario>/
  expected.json        # the verdict a verifier should return
  repo/
    src/...            # the invented source tree
    docs/<block>/      # a complete block: README, CONTRACTS, INVARIANTS, GAPS, OPERATIONS
```

Every page uses `verified_against: PIN` as a placeholder. The block is correct except for one planted wrong section. `expected.json` names it:

```json
{"section": "INVARIANTS.md > 1. Heading text", "verdict": "wrong", "class": "OVERGENERALIZED", "why": "..."}
```

`section` is the page file and the exact heading text. `verdict` and `class` use the verifier's closed lists.

| Scenario | Trap | Expected class |
|---|---|---|
| `polarity` | A comment says two tiers are excluded; the predicate includes them. | `POLARITY` |
| `overgeneralized` | Three producers enqueue jobs; only one sets a dedupe key. | `OVERGENERALIZED` |
| `unreachable` | The visibility filter sits in a helper that nothing calls. | `UNREACHABLE` |
| `cross_boundary_absence` | A table documented as read-only is written from another block. | `CROSS_BOUNDARY_ABSENCE` |
| `intent_as_fact` | Middleware documented as validating a session only checks the cookie is present. | `INTENT_AS_FACT` |

The planted sections that use an absolute word carry a `scope:` line that is too narrow, so they pass the structural linter. Only a claim check catches them.

## Run the verifier

1. Copy the scenario's source tree to a temporary directory and commit it:

   ```sh
   work="$(mktemp -d)"
   cp -R evals/polarity/repo/. "$work"
   git -C "$work" init -q
   git -C "$work" add -A
   git -C "$work" -c user.name=eval -c user.email=eval@example.invalid commit -qm "eval fixture"
   pin="$(git -C "$work" rev-parse --short HEAD)"
   ```

2. Fill the pin into the docs front matter. Leave the change uncommitted; the pin is still an ancestor of `HEAD`:

   ```sh
   find "$work/docs" -name '*.md' -exec sed -i.bak "s/^verified_against: PIN$/verified_against: $pin/" {} \; -exec rm -f {}.bak \;
   ```

3. Optionally confirm the block is structurally clean:

   ```sh
   python3 scripts/blockdocs_lint.py "$work/docs" --repo "$work"
   ```

4. Dispatch `block-docs-verifier` with this brief, filling in the scenario's block and owned paths from its `README.md`:

   ```text
   docs_root: <work>/docs
   source_root: <work>
   pin: <pin>
   block_id: entitlements
   pages: [CONTRACTS.md, INVARIANTS.md, GAPS.md]
   owned_paths: [src/entitlements/]
   plugin_root: <absolute path to this checkout, if outside the loader>
   ```

5. Compare the result with `expected.json`. A pass needs the named section with the expected verdict and class, evidence that includes the command or quoted expression that exposes the trap, and replacement text that fixes it. Record any other section the verifier marks as not `correct`: either the scenario has a second error to fix, or the verifier produced a false positive.

For `intent_as_fact` and `unreachable`, the report should also list a suspected code bug.

## Run the writer

The same source tree tests whether the writer avoids the trap.

1. Follow step 1 above, then delete `docs/<block>/` from the copy and commit again so the pin has no answer key in it.
2. Dispatch `block-docs-writer` for the same block, with the new pin, the `owns:` paths from the original `README.md`, `mode: code`, and `allowed_files` set to the five block pages.
3. Read the section the writer produced for the trapped behavior. A pass states the behavior correctly, or narrows the claim and records the rest in `GAPS.md`. It must not repeat the planted claim. An absolute word must come with a `scope:` line that covers the whole source root.
4. Run the verifier on the writer's output as above. The trapped section should come back `correct`.

## Add a scenario

Keep the source small and invented. Do not copy code, names, or data from a real system. Make every section except the planted one correct at the pin, cite with `path::symbol` or `path::"quoted phrase"` forms that exist in the source, and add the scenario to the table above.
