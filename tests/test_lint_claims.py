"""Checks for claim quality: evidence tag forms, scoped absolute claims,
verified-citation pairing, and pin drift.
"""

from pathlib import Path
from typing import Optional

import pytest

from test_lint import (
    FixtureRepo,
    commit_all,
    finding_codes,
    git,
    make_good_repo,
    page_text,
    replace_pin,
    run_lint,
    write_block,
)


def test_colon_form_verified_tag_satisfies_evidence_check(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    operations = fixture.docs / "alpha" / "OPERATIONS.md"
    operations.write_text(
        page_text(
            block="alpha",
            doc="OPERATIONS",
            pin=fixture.pin,
            body="# Operations\n\nThe operations record. [verified: src/x.py::f()]",
        ),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert "W003" not in finding_codes(result), result.stdout


def _write_page(fixture: FixtureRepo, doc: str, body: str, pin: Optional[str] = None) -> Path:
    target = fixture.docs / "alpha" / f"{doc}.md"
    target.write_text(
        page_text(block="alpha", doc=doc, pin=pin or fixture.pin, body=body),
        encoding="utf-8",
    )
    return target


@pytest.mark.parametrize("doc", ["CONTRACTS", "INVARIANTS"])
def test_w004_fires_on_unscoped_absolute_claim(tmp_path: Path, doc: str) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        doc,
        "# {}\n\n".format(doc.title())
        + "## Producer identity\n\n"
        + "Every producer sets a job id. [verified]\n\n"
        + "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W004") == 1, result.stdout
    assert "absolute claim has no scope line in this section" in result.stdout


def test_w004_silent_when_section_declares_scope(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "scope: git grep -n queue.add <pin> -- src/\n\n"
        "Every producer sets a job id. [verified]\n\n"
        "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert "W004" not in finding_codes(result), result.stdout


def test_w004_silent_for_inferred_tag(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "Every producer sets a job id. [inferred]\n\n"
        "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert "W004" not in finding_codes(result), result.stdout


def test_w004_silent_when_absolute_word_only_in_backticks(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "The rule covers `all` cases with `onlyOnce()`. [verified]\n\n"
        "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert "W004" not in finding_codes(result), result.stdout


def test_w004_silent_in_spec_mode(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "Every producer sets a job id. [verified]\n\n"
        "enforcement: planned: `src/service.py::enforce_rule()`",
        pin="spec@" + fixture.pin,
    )

    result = run_lint(fixture, "--no-git")

    assert "W004" not in finding_codes(result), result.stdout


@pytest.mark.parametrize("doc", ["GAPS", "OPERATIONS"])
def test_w004_silent_outside_contracts_and_invariants(tmp_path: Path, doc: str) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        doc,
        "# {}\n\n".format(doc.title())
        + "## Producer identity\n\n"
        + "Every producer sets a job id. [verified]",
    )

    result = run_lint(fixture)

    assert "W004" not in finding_codes(result), result.stdout


def test_w004_reports_one_finding_per_section_with_several_offending_lines(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "Every producer sets a job id. [verified]\n\n"
        "Only one producer claims a shard. [verified]\n\n"
        "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W004") == 1, result.stdout


def test_w005_fires_on_verified_claim_without_citation(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\nThe worker retries three times. [verified]",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W005") == 1, result.stdout
    assert "verified claim has no recognized citation" in result.stdout


def test_w005_silent_with_backticked_prose_citation(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n`src/worker.py::retry()` retries three times. [verified]",
    )

    result = run_lint(fixture)

    assert "W005" not in finding_codes(result), result.stdout


def test_w005_silent_with_colon_tag_citation(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\nThe worker retries three times. [verified: src/worker.py::retry()]",
    )

    result = run_lint(fixture)

    assert "W005" not in finding_codes(result), result.stdout


def test_w005_silent_for_inferred_tag(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\nThe worker retries three times. [inferred]",
    )

    result = run_lint(fixture)

    assert "W005" not in finding_codes(result), result.stdout


def test_w005_silent_in_spec_mode(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\nThe worker retries three times. [verified]",
        pin="spec@" + fixture.pin,
    )

    result = run_lint(fixture, "--no-git")

    assert "W005" not in finding_codes(result), result.stdout


def test_drift_w006_fires_when_cited_file_changed_after_pin(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    new_ref = commit_all(fixture.root, "change service")

    result = run_lint(fixture, "--drift", new_ref)

    assert result.returncode == 0, result.stdout + result.stderr
    # 4, not 1: the default fixture's CONTRACTS, INVARIANTS, GAPS and OPERATIONS
    # pages each cite src/service.py, one page per colon-tag citation now that
    # _extract_citations also reads colon-detail citations (README's plain
    # [verified] carries no citation, so it stays silent).
    assert finding_codes(result).count("W006") == 4, result.stdout
    assert "src/service.py" in result.stdout


def test_drift_w007_fires_on_revert_commit_touching_owned_path(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    new_ref = commit_all(fixture.root, 'Revert "enforce rule"')

    result = run_lint(fixture, "--drift", new_ref)

    assert finding_codes(result).count("W007") == 1, result.stdout
    assert new_ref[:12] in result.stdout
    assert "Revert" in result.stdout


def test_drift_silent_when_untouched(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
    new_ref = commit_all(fixture.root, "unrelated change")

    result = run_lint(fixture, "--drift", new_ref)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "W006" not in finding_codes(result), result.stdout
    assert "W007" not in finding_codes(result), result.stdout


def test_drift_rejects_no_git_combination(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)

    result = run_lint(fixture, "--drift", fixture.pin, "--no-git")

    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""
    assert "--drift" in result.stderr
    assert "--no-git" in result.stderr


def test_drift_rejects_unknown_ref(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)

    result = run_lint(fixture, "--drift", "0123456789abcdef0123456789abcdef01234567")

    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""


def test_drift_w006_strict_exits_nonzero(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    new_ref = commit_all(fixture.root, "change service")

    normal = run_lint(fixture, "--drift", new_ref)
    strict = run_lint(fixture, "--drift", new_ref, "--strict")

    assert normal.returncode == 0, normal.stdout + normal.stderr
    assert strict.returncode == 1, strict.stdout + strict.stderr


def test_drift_disabled_without_flag_even_with_changes(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    commit_all(fixture.root, "change service")

    result = run_lint(fixture)

    assert "W006" not in finding_codes(result), result.stdout
    assert "W007" not in finding_codes(result), result.stdout


def test_e006_fires_on_bogus_colon_citation(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\nThe operations record. [verified: src/missing.py::nope()]",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("E006") == 1, result.stdout
    assert "src/missing.py" in result.stdout


def test_colon_citation_trailing_prose_still_parses(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\nThe operations record. "
        "[verified: src/service.py::enforce_rule(); corrected 2026-09-26, earlier text was wrong]",
    )

    result = run_lint(fixture)

    assert "E006" not in finding_codes(result), result.stdout


def test_colon_citation_with_bracketed_quoted_symbol_still_parses(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n"
        "    return rows[0] if rows else None\n",
        encoding="utf-8",
    )
    new_pin = commit_all(fixture.root, "add bracket literal")
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n"
        'The operations record. [verified: src/service.py::"rows[0] if rows else None"]',
        pin=new_pin,
    )

    result = run_lint(fixture)

    assert "E006" not in finding_codes(result), result.stdout


def test_colon_citation_with_quoted_semicolon_statement_still_parses(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n"
        "    res.status(401).end();\n",
        encoding="utf-8",
    )
    new_pin = commit_all(fixture.root, "add semicolon statement")
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n"
        'The operations record. [verified: src/service.py::"res.status(401).end();"]',
        pin=new_pin,
    )

    result = run_lint(fixture)

    assert "E006" not in finding_codes(result), result.stdout


def test_drift_w006_fires_on_colon_only_citation(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    new_ref = commit_all(fixture.root, "change service")

    result = run_lint(fixture, "--drift", new_ref)

    invariants_lines = [
        line
        for line in result.stdout.splitlines()
        if "INVARIANTS.md" in line and "W006" in line
    ]
    assert len(invariants_lines) == 1, result.stdout
    assert "src/service.py" in invariants_lines[0]


def test_w005_silent_when_leaf_section_has_scope_line(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "GAPS",
        "# Gaps\n\n"
        "## No tests\n\n"
        "The source tree has no test files. [verified]\n\n"
        "scope: `git ls-tree -r --name-only <pin>` (no test files listed)",
    )

    result = run_lint(fixture)

    assert "W005" not in finding_codes(result), result.stdout


def test_w005_fires_in_leaf_section_without_scope_line(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "GAPS",
        "# Gaps\n\n"
        "## No tests\n\n"
        "The source tree has no test files. [verified]",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W005") == 1, result.stdout


def test_w005_silent_in_readme(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    readme = fixture.docs / "alpha" / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace(
        "The block overview. [verified]",
        "The block overview. The worker retries three times. [verified]",
    )
    readme.write_text(text, encoding="utf-8")

    result = run_lint(fixture)

    assert "W005" not in finding_codes(result), result.stdout


# --- Item 1: an apostrophe in colon-tag prose must not swallow the citation ---


def test_e006_fires_despite_apostrophe_in_colon_detail_prose(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n"
        "The operations record. [verified: src/missing.py::nope(); the writer's note]",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("E006") == 1, result.stdout
    assert "src/missing.py" in result.stdout
    # W005 must agree with E006: a citation was recognized (and rejected by
    # E006 for a bad target), so this is not "no citation at all".
    assert "W005" not in finding_codes(result), result.stdout


# --- Item 2: a backtick-wrapped colon-detail citation is already covered by
# the inline-code pass; parsing it again corrupts its path and double-counts
# it. ---


def test_e006_silent_for_backtick_wrapped_colon_detail_citation(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n"
        "The operations record. [verified: `src/service.py::enforce_rule()`]",
    )

    result = run_lint(fixture)

    assert "E006" not in finding_codes(result), result.stdout
    assert "`src/service.py" not in result.stdout


def test_colon_detail_backtick_citation_not_double_counted_for_spec_pins(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    for page in fixture.docs.rglob("*.md"):
        replace_pin(page, fixture.pin, "spec@" + fixture.pin)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n"
        "The operations record. [verified: `src/service.py::enforce_rule()`]",
        pin="spec@" + fixture.pin,
    )

    result = run_lint(fixture, "--no-git")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "E006" not in finding_codes(result), result.stdout
    # 5, not 6: the backtick-wrapped colon-detail citation is the same one the
    # inline-code pass already found on this line; it must count once.
    assert "5 code citations skipped for spec pin" in result.stdout


# --- Item 3: W007 revert matching (Conventional Commits form, merge
# reverts, non-ASCII owned paths). ---


def test_drift_w007_matches_conventional_commit_revert_subject(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    new_ref = commit_all(fixture.root, "revert: undo enforce rule change")

    result = run_lint(fixture, "--drift", new_ref)

    assert finding_codes(result).count("W007") == 1, result.stdout


def test_drift_w007_matches_merge_revert_paths(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    git(fixture.root, "checkout", "-q", "-b", "topic")
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    git(fixture.root, "add", "-A")
    git(fixture.root, "commit", "-q", "-m", "break rule")
    git(fixture.root, "checkout", "-q", "main")
    git(fixture.root, "merge", "--no-ff", "-m", 'Revert "break rule"', "topic")
    new_ref = git(fixture.root, "rev-parse", "HEAD")

    result = run_lint(fixture, "--drift", new_ref)

    assert finding_codes(result).count("W007") == 1, result.stdout


def test_drift_w007_matches_non_ascii_owned_path_despite_local_quote_path(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    # Force quoting even if the host machine's global git config disables it,
    # so this test cannot pass by accident of the environment.
    git(fixture.root, "config", "core.quotePath", "true")
    readme = fixture.docs / "alpha" / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(
        text.replace("owns: [src/service.py]", "owns: [src/service.py, src/café.py]"),
        encoding="utf-8",
    )
    (fixture.root / "src" / "café.py").write_text("VALUE = 1\n", encoding="utf-8")
    commit_all(fixture.root, "add cafe module")
    (fixture.root / "src" / "café.py").write_text("VALUE = 2\n", encoding="utf-8")
    new_ref = commit_all(fixture.root, 'Revert "add cafe module"')

    result = run_lint(fixture, "--drift", new_ref)

    assert finding_codes(result).count("W007") == 1, result.stdout


# --- Item 4: W004 must also scan text before the first heading, and a
# parent `##` group's intro text before its first `###` child. ---


def test_w004_fires_on_text_before_first_heading(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "Every rule holds without exception. [verified]\n\n"
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "scope: `git grep -n foo <pin> -- src/`\n\n"
        "One producer sets an id. [verified: src/service.py::enforce_rule()]\n\n"
        "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W004") == 1, result.stdout


def test_w004_fires_on_group_intro_before_first_child(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "Every producer sets a job id. [verified]\n\n"
        "### Detail one\n\n"
        "scope: `src/foo.py`\n\n"
        "Some detail. [verified: src/service.py::enforce_rule()]\n\n"
        "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W004") == 1, result.stdout


# --- Item 5: W005 block boundaries: a wrapped list item's indented
# continuation line, and a claim directly after a heading with no blank
# line. ---


def test_w005_silent_when_citation_is_on_wrapped_list_item_continuation(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n"
        "- The worker retries three times. [verified]\n"
        "  See `src/service.py::enforce_rule()` for the retry logic.\n",
    )

    result = run_lint(fixture)

    assert "W005" not in finding_codes(result), result.stdout


def test_w005_silent_when_heading_directly_precedes_claim_in_scoped_section(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "GAPS",
        "# Gaps\n\n"
        "## No tests\n"
        "The source tree has no test files. [verified]\n\n"
        "scope: `git ls-tree -r --name-only <pin>` (no test files listed)",
    )

    result = run_lint(fixture)

    assert "W005" not in finding_codes(result), result.stdout


# --- Item 6: W004 must ignore absolute words that appear only inside a
# colon-tag citation detail or an enforcement: line. ---


def test_w004_silent_for_colon_tag_detail_and_enforcement_noise(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        'The rule behaves as expected. [verified: src/a.py::"return None"]\n'
        "enforcement: `src/service.py::enforce_rule()` (every route)\n",
    )

    result = run_lint(fixture)

    assert "W004" not in finding_codes(result), result.stdout


# --- Item 7: a `scope:` value only counts when it names a command or a path
# set (backtick or `/`); `none` and `n/a` are placeholders, not scope. ---


@pytest.mark.parametrize("placeholder", ["none", "n/a"])
def test_w004_fires_when_scope_value_is_placeholder(
    tmp_path: Path, placeholder: str
) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "CONTRACTS",
        "# Contracts\n\n"
        "## Producer identity\n\n"
        "scope: {}\n\n".format(placeholder)
        + "Every producer sets a job id. [verified]\n\n"
        + "enforcement: `src/service.py::enforce_rule()`",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W004") == 1, result.stdout


@pytest.mark.parametrize("placeholder", ["none", "n/a"])
def test_w005_fires_when_scope_value_is_placeholder(
    tmp_path: Path, placeholder: str
) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "GAPS",
        "# Gaps\n\n"
        "## No tests\n\n"
        "scope: {}\n\n".format(placeholder)
        + "The source tree has no test files. [verified]",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W005") == 1, result.stdout


# --- Item 8: a --drift REF that is not a descendant of a page's pin skips
# drift checks for that page and prints one note line, exit code unaffected. ---


def test_drift_notes_instead_of_checking_when_ref_is_not_descendant_of_pin(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    git(fixture.root, "checkout", "-q", "--orphan", "unrelated")
    (fixture.root / "src" / "service.py").write_text(
        "def enforce_rule():\n    return False\n", encoding="utf-8"
    )
    git(fixture.root, "add", "-A")
    git(fixture.root, "commit", "-q", "-m", "unrelated history")
    unrelated_ref = git(fixture.root, "rev-parse", "HEAD")
    git(fixture.root, "checkout", "-q", "main")

    result = run_lint(fixture, "--drift", unrelated_ref)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "W006" not in finding_codes(result), result.stdout
    assert "W007" not in finding_codes(result), result.stdout
    assert "is not a descendant of pin" in result.stdout


# --- Review follow-up: claims directly under the H1 title, and prose around a
# backticked citation inside a colon detail. ---


def test_w004_fires_on_claim_under_title_before_first_section(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "INVARIANTS",
        "# Invariants\n\n"
        "Every producer sets a job id. [verified: src/service.py::enforce_rule()]\n\n"
        "## Parent\n\n"
        "scope: `git grep -n foo <pin> -- src/`\n\n"
        "One rule holds. [verified: src/service.py::enforce_rule()]",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W004") == 1, result.stdout
    assert "INVARIANTS.md:10: W004" in result.stdout, result.stdout


def test_w004_fires_on_flat_list_under_title_only(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "INVARIANTS",
        "# Invariants\n\n"
        "- Every producer sets a job id. [verified: src/service.py::enforce_rule()]\n"
        "- Only one shard writes. [verified: src/service.py::enforce_rule()]",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("W004") == 1, result.stdout


def test_colon_detail_with_prose_around_backticked_citation_is_not_e006(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    _write_page(
        fixture,
        "OPERATIONS",
        "# Operations\n\n"
        "The operations record. [verified: see `src/service.py::enforce_rule()` for details]",
    )

    result = run_lint(fixture)

    assert "E006" not in finding_codes(result), result.stdout
    assert "W005" not in finding_codes(result), result.stdout
