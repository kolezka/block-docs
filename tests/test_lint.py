from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pytest


SCRIPT = Path(
    os.environ.get(
        "BLOCKDOCS_LINT_SCRIPT",
        Path(__file__).resolve().parents[1] / "scripts" / "blockdocs_lint.py",
    )
)
MANDATORY_DOCS = ("README", "CONTRACTS", "INVARIANTS", "GAPS", "OPERATIONS")


@dataclass
class FixtureRepo:
    root: Path
    docs: Path
    pin: str


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(repo: Path, *args: str) -> str:
    return run_command(("git", *args), cwd=repo).stdout.strip()


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "--short=12", "HEAD")


def page_text(
    *,
    block: str,
    doc: str,
    pin: str,
    body: str,
    owns: Optional[Iterable[str]] = None,
    depends_on: Optional[Iterable[str]] = None,
) -> str:
    lines = [
        "---",
        f"block: {block}",
        f"doc: {doc}",
        f"verified_against: {pin}",
        "verified_on: 2026-09-06",
    ]
    if owns is not None:
        lines.append(f"owns: [{', '.join(owns)}]")
    if depends_on is not None:
        lines.append(f"depends_on: [{', '.join(depends_on)}]")
    lines.extend(("---", "", body.rstrip(), ""))
    return "\n".join(lines)


def write_block(
    docs: Path,
    name: str,
    pin: str,
    *,
    owns: Iterable[str],
    block_value: Optional[str] = None,
) -> Path:
    block_dir = docs / name
    block_dir.mkdir(parents=True, exist_ok=True)
    declared_block = block_value or name
    for doc in MANDATORY_DOCS:
        if doc == "README":
            body = f"# {name}\n\nThe block overview. [verified]"
            text = page_text(
                block=declared_block,
                doc=doc,
                pin=pin,
                body=body,
                owns=owns,
                depends_on=[],
            )
        elif doc == "CONTRACTS":
            body = (
                "# Contracts\n\n"
                "## Enforced rule\n\n"
                "The service keeps the rule. [verified]\n\n"
                "enforcement: `src/service.py::enforce_rule()`"
            )
            text = page_text(block=declared_block, doc=doc, pin=pin, body=body)
        else:
            body = f"# {doc.title()}\n\nThe {doc.lower()} record. [verified]"
            text = page_text(block=declared_block, doc=doc, pin=pin, body=body)
        (block_dir / f"{doc}.md").write_text(text, encoding="utf-8")
    return block_dir


def make_good_repo(tmp_path: Path) -> FixtureRepo:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Block Docs Tests")
    git(repo, "config", "user.email", "block-docs@example.invalid")
    source = repo / "src" / "service.py"
    source.parent.mkdir()
    source.write_text(
        "CONTRACT_TEXT = \"literal contract\"\n\n"
        "def enforce_rule():\n"
        "    return True\n",
        encoding="utf-8",
    )
    pin = commit_all(repo, "add source")
    docs = repo / "docs"
    write_block(docs, "alpha", pin, owns=["src/service.py"])
    commit_all(repo, "add docs")
    return FixtureRepo(root=repo, docs=docs, pin=pin)


def run_lint(
    fixture: FixtureRepo,
    *args: str,
    docs: Optional[Path] = None,
) -> subprocess.CompletedProcess[str]:
    command: List[str] = [
        sys.executable,
        str(SCRIPT),
        str(docs or fixture.docs),
        "--repo",
        str(fixture.root),
        *args,
    ]
    return run_command(command, cwd=fixture.root, check=False)


def finding_codes(result: subprocess.CompletedProcess[str]) -> List[str]:
    return re.findall(r": (E\d{3}|W\d{3})(?: |$)", result.stdout)


def assert_finding(
    result: subprocess.CompletedProcess[str],
    code: str,
    message_fragment: str,
) -> None:
    assert result.returncode == 1, result.stdout + result.stderr
    assert code in finding_codes(result), result.stdout
    assert message_fragment in result.stdout, result.stdout


def replace_line(path: Path, prefix: str, replacement: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    assert len(matches) == 1
    lines[matches[0]] = replacement
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def replace_pin(path: Path, old_pin: str, new_pin: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert f"verified_against: {old_pin}" in text
    path.write_text(
        text.replace(f"verified_against: {old_pin}", f"verified_against: {new_pin}"),
        encoding="utf-8",
    )


def test_good_tree_has_no_findings(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)

    result = run_lint(fixture)

    assert result.returncode == 0, result.stdout + result.stderr
    assert finding_codes(result) == []
    assert "Summary: 0 errors, 0 warnings, 5 files scanned" in result.stdout


@pytest.mark.parametrize(
    ("mutate", "message_fragment"),
    [
        ("missing-front-matter", "front matter is missing"),
        ("unsupported-yaml", "unsupported front matter syntax"),
        ("missing-field", "missing required field 'doc'"),
        ("empty-field", "field 'doc' must not be empty"),
        ("wrong-owns-type", "field 'owns' must be a flow-style list"),
        ("empty-owns", "field 'owns' must not be empty"),
        ("bad-date", "field 'verified_on' must be a valid YYYY-MM-DD date"),
        (
            "bad-pin",
            "field 'verified_against' must be a short commit SHA or spec@SHA",
        ),
        ("owns-on-non-readme", "field 'owns' is only allowed on a block README"),
    ],
)
def test_e001_rejects_invalid_front_matter(
    tmp_path: Path,
    mutate: str,
    message_fragment: str,
) -> None:
    fixture = make_good_repo(tmp_path)
    readme = fixture.docs / "alpha" / "README.md"
    operations = fixture.docs / "alpha" / "OPERATIONS.md"

    if mutate == "missing-front-matter":
        operations.write_text("# Operations\n\nNo metadata.\n", encoding="utf-8")
    elif mutate == "unsupported-yaml":
        text = readme.read_text(encoding="utf-8")
        readme.write_text(
            text.replace("owns: [src/service.py]", "owns:\n  - src/service.py"),
            encoding="utf-8",
        )
    elif mutate == "missing-field":
        text = operations.read_text(encoding="utf-8")
        operations.write_text(
            text.replace("doc: OPERATIONS\n", ""), encoding="utf-8"
        )
    elif mutate == "empty-field":
        replace_line(operations, "doc:", "doc:")
    elif mutate == "wrong-owns-type":
        replace_line(readme, "owns:", "owns: src/service.py")
    elif mutate == "empty-owns":
        replace_line(readme, "owns:", "owns: []")
    elif mutate == "bad-date":
        replace_line(operations, "verified_on:", "verified_on: 2026-02-30")
    elif mutate == "bad-pin":
        replace_line(operations, "verified_against:", "verified_against: latest")
    elif mutate == "owns-on-non-readme":
        text = operations.read_text(encoding="utf-8")
        operations.write_text(
            text.replace("verified_on: 2026-09-06", "verified_on: 2026-09-06\nowns: [src/service.py]"),
            encoding="utf-8",
        )
    else:
        raise AssertionError(f"unknown mutation: {mutate}")

    result = run_lint(fixture)

    assert_finding(result, "E001", message_fragment)


@pytest.mark.parametrize(
    ("relative_path", "declared_block", "message_fragment"),
    [
        ("alpha/OPERATIONS.md", "wrong", "must equal containing directory 'alpha'"),
        ("OWNERSHIP.md", "alpha", "root page block must be '_root'"),
    ],
)
def test_e002_rejects_wrong_block_identity(
    tmp_path: Path,
    relative_path: str,
    declared_block: str,
    message_fragment: str,
) -> None:
    fixture = make_good_repo(tmp_path)
    target = fixture.docs / relative_path
    if target.parent == fixture.docs:
        target.write_text(
            page_text(
                block=declared_block,
                doc="OWNERSHIP",
                pin=fixture.pin,
                body="# Ownership\n\nRoot ownership text.",
            ),
            encoding="utf-8",
        )
    else:
        replace_line(target, "block:", f"block: {declared_block}")

    result = run_lint(fixture)

    assert_finding(result, "E002", message_fragment)


def test_e003_rejects_doc_filename_mismatch(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    operations = fixture.docs / "alpha" / "OPERATIONS.md"
    replace_line(operations, "doc:", "doc: RUNBOOK")

    result = run_lint(fixture)

    assert_finding(result, "E003", "must match filename 'OPERATIONS.md'")


def test_e003_accepts_uppercase_kebab_root_and_extra_block_pages(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    for doc in (
        "README",
        "CONVENTIONS",
        "GLOSSARY",
        "DATA-FLOW",
        "OWNERSHIP",
        "MIGRATION",
    ):
        (fixture.docs / f"{doc}.md").write_text(
            page_text(
                block="_root",
                doc=doc,
                pin=fixture.pin,
                body=f"# {doc}\n\nRoot page.",
            ),
            encoding="utf-8",
        )
    (fixture.docs / "alpha" / "PERMISSIONS.md").write_text(
        page_text(
            block="alpha",
            doc="PERMISSIONS",
            pin=fixture.pin,
            body="# Permissions\n\nThe permissions contract. [verified]",
        ),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "E003" not in finding_codes(result)


def test_e003_rejects_non_uppercase_kebab_doc(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    extra = fixture.docs / "alpha" / "Runbook.md"
    extra.write_text(
        page_text(
            block="alpha",
            doc="Runbook",
            pin=fixture.pin,
            body="# Runbook\n\nA page. [verified]",
        ),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert_finding(result, "E003", "must be README or uppercase kebab-case")


def test_e004_finds_incomplete_block_when_readme_was_removed(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.docs / "alpha" / "README.md").unlink()

    result = run_lint(fixture)

    assert_finding(result, "E004", "block is missing mandatory file: README.md")


@pytest.mark.parametrize("prefix", ["src/x/", "src/x/**"])
def test_e005_compares_component_prefixes_between_directory_owners(
    tmp_path: Path,
    prefix: str,
) -> None:
    fixture = make_good_repo(tmp_path)
    alpha = fixture.docs / "alpha"
    write_block(
        fixture.docs,
        "beta",
        fixture.pin,
        owns=["src/x/file.py", "src/abc"],
        block_value="shared",
    )
    for path in alpha.glob("*.md"):
        replace_line(path, "block:", "block: shared")
    replace_line(
        alpha / "README.md",
        "owns:",
        f"owns: [{prefix}, src/ab, src/repeated, src/repeated]",
    )

    result = run_lint(fixture)

    assert result.returncode == 1
    assert finding_codes(result).count("E005") == 1, result.stdout
    assert "owned by both 'alpha' and 'beta'" in result.stdout
    assert "src/ab" not in "\n".join(
        line for line in result.stdout.splitlines() if ": E005 " in line
    )


@pytest.mark.parametrize(
    ("citation", "message_fragment"),
    [
        ("missing/file.py::symbol()", "citation path 'missing/file.py' is absent at pin"),
        ("src/service.py::missing_symbol()", "citation symbol 'missing_symbol' was not found at pin"),
    ],
)
def test_e006_rejects_missing_pinned_citation_targets(
    tmp_path: Path,
    citation: str,
    message_fragment: str,
) -> None:
    fixture = make_good_repo(tmp_path)
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8")
    contracts.write_text(
        text.replace("src/service.py::enforce_rule()", citation),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert_finding(result, "E006", message_fragment)


def test_e006_reads_code_from_pin_not_dirty_checkout(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "service.py").write_text(
        "def replacement():\n    return False\n", encoding="utf-8"
    )

    pinned_result = run_lint(fixture)
    working_tree_result = run_lint(fixture, "--no-git")

    assert pinned_result.returncode == 0, pinned_result.stdout + pinned_result.stderr
    assert "E006" not in finding_codes(pinned_result)
    assert_finding(
        working_tree_result,
        "E006",
        "citation symbol 'enforce_rule' was not found in --repo file",
    )


def test_e006_skips_target_citations_for_spec_pins_and_reports_limit(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    for page in fixture.docs.rglob("*.md"):
        replace_pin(page, fixture.pin, f"spec@{fixture.pin}")
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8")
    contracts.write_text(
        text.replace(
            "src/service.py::enforce_rule()",
            "planned/not-created.py::future_symbol()",
        ),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "E006" not in finding_codes(result)
    assert "1 code citation skipped for spec pin" in result.stdout


def test_e006_accepts_quoted_phrase_at_pin(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8")
    contracts.write_text(
        text.replace(
            "src/service.py::enforce_rule()",
            'src/service.py::"literal contract"',
        ),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "E006" not in finding_codes(result)


def test_e006_ignores_citation_examples_inside_fenced_code(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    operations = fixture.docs / "alpha" / "OPERATIONS.md"
    text = operations.read_text(encoding="utf-8")
    operations.write_text(
        text
        + "\n```markdown\n`missing/example.py::not_real()` [verified]\n```\n",
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "E006" not in finding_codes(result)


@pytest.mark.parametrize("citation", ["../outside-secret.txt::DO_NOT_READ", "leak.txt::DO_NOT_READ"])
def test_e006_refuses_path_escape_without_reading_outside_repo(
    tmp_path: Path,
    citation: str,
) -> None:
    fixture = make_good_repo(tmp_path)
    secret = fixture.root.parent / "outside-secret.txt"
    secret_value = "DO_NOT_READ_SECRET_7c3f"
    secret.write_text(secret_value, encoding="utf-8")
    if citation.startswith("leak.txt"):
        os.symlink(secret, fixture.root / "leak.txt")
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8")
    contracts.write_text(
        text.replace("src/service.py::enforce_rule()", citation),
        encoding="utf-8",
    )

    result = run_lint(fixture, "--no-git")

    assert_finding(result, "E006", "escapes --repo")
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr


def test_e001_refuses_markdown_symlink_outside_repo_without_reading_it(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    secret = fixture.root.parent / "outside-doc.md"
    secret_value = "DO_NOT_READ_DOC_SECRET_2a41"
    secret.write_text(secret_value, encoding="utf-8")
    os.symlink(secret, fixture.docs / "alpha" / "SECRETS.md")

    result = run_lint(fixture)

    assert_finding(result, "E001", "Markdown path escapes --repo")
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr


def test_e007_fails_loud_for_unavailable_pin_without_citation_fallback(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    for page in fixture.docs.rglob("*.md"):
        replace_pin(page, fixture.pin, "deadbeef")
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8")
    contracts.write_text(
        text.replace("src/service.py::enforce_rule()", "missing/current.py::symbol()"),
        encoding="utf-8",
       )

    result = run_lint(fixture)

    assert_finding(result, "E007", "pin 'deadbeef' is not available in --repo")
    assert "E006" not in finding_codes(result), result.stdout


def test_e007_rejects_commit_that_is_not_an_ancestor_of_head(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    git(fixture.root, "checkout", "-q", "-b", "side")
    (fixture.root / "side.txt").write_text("side\n", encoding="utf-8")
    side_pin = commit_all(fixture.root, "side commit")
    git(fixture.root, "checkout", "-q", "main")
    for page in fixture.docs.rglob("*.md"):
        replace_pin(page, fixture.pin, side_pin)

    result = run_lint(fixture)

    assert_finding(result, "E007", f"pin '{side_pin}' is not an ancestor of HEAD")


def test_no_git_skips_ancestry_and_uses_repo_files(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    for page in fixture.docs.rglob("*.md"):
        replace_pin(page, fixture.pin, "deadbeef")

    result = run_lint(fixture, "--no-git")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "E007" not in finding_codes(result)
    assert "E006" not in finding_codes(result)


@pytest.mark.parametrize(
    ("body", "expected_count"),
    [
        (
            "# Contracts\n\n"
            "## Group\n\nShared context. [verified]\n\n"
            "### Concrete contract\n\nThe rule. [verified]\n\n"
            "enforcement:",
            1,
        ),
        (
            "# Contracts\n\n"
            "## Leaf contract\n\nThe rule. [verified]",
            1,
        ),
        (
            "# Contracts\n\n"
            "## Leaf contract\n\nThe rule. [verified]\n\n"
            "```text\n"
            "enforcement: example only\n"
            "```",
            1,
        ),
        (
            "# Contracts\n\n"
            "## Group\n\nShared context. [verified]\n\n"
            "### Concrete contract\n\nThe rule. [verified]\n\n"
            "enforcement: convention",
            0,
        ),
    ],
)
def test_e008_requires_nonempty_enforcement_on_concrete_contracts(
    tmp_path: Path,
    body: str,
    expected_count: int,
) -> None:
    fixture = make_good_repo(tmp_path)
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    contracts.write_text(
        page_text(
            block="alpha",
            doc="CONTRACTS",
            pin=fixture.pin,
            body=body,
        ),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert finding_codes(result).count("E008") == expected_count, result.stdout
    if expected_count:
        assert result.returncode == 1
        assert "contract entry has no nonempty enforcement: value" in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr


def test_w001_reports_multiple_pins_and_strict_makes_warning_fail(
    tmp_path: Path,
) -> None:
    fixture = make_good_repo(tmp_path)
    (fixture.root / "src" / "second.py").write_text("SECOND = True\n", encoding="utf-8")
    second_pin = commit_all(fixture.root, "second source")
    replace_pin(fixture.docs / "alpha" / "OPERATIONS.md", fixture.pin, second_pin)

    normal = run_lint(fixture)
    strict = run_lint(fixture, "--strict")

    assert normal.returncode == 0, normal.stdout + normal.stderr
    assert finding_codes(normal).count("W001") == 1, normal.stdout
    assert "tree contains more than one verified_against pin" in normal.stdout
    assert strict.returncode == 1, strict.stdout + strict.stderr
    assert finding_codes(strict).count("W001") == 1


def test_w002_reports_long_dash_only_in_prose(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    operations = fixture.docs / "alpha" / "OPERATIONS.md"
    text = operations.read_text(encoding="utf-8")
    operations.write_text(
        text
        + "\nA prose clause — another clause. [verified]\n"
        + "```text\nAn example — ignored.\n```\n",
        encoding="utf-8",
    )

    normal = run_lint(fixture)
    strict = run_lint(fixture, "--strict")

    assert normal.returncode == 0, normal.stdout + normal.stderr
    assert finding_codes(normal).count("W002") == 1, normal.stdout
    assert "prose contains an en dash or em dash" in normal.stdout
    assert strict.returncode == 1


def test_w003_does_not_accept_unknown_evidence_tag(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    operations = fixture.docs / "alpha" / "OPERATIONS.md"
    text = operations.read_text(encoding="utf-8")
    operations.write_text(text.replace("[verified]", "[guessed]"), encoding="utf-8")
    (fixture.docs / "OWNERSHIP.md").write_text(
        page_text(
            block="_root",
            doc="OWNERSHIP",
            pin=fixture.pin,
            body="# Ownership\n\nRoot prose needs no block evidence tag check.",
        ),
        encoding="utf-8",
    )

    result = run_lint(fixture)

    assert result.returncode == 0, result.stdout + result.stderr
    assert finding_codes(result).count("W003") == 1, result.stdout
    assert "block page has no recognized evidence tag" in result.stdout


@pytest.mark.parametrize("only_exempt", [False, True])
def test_e999_rejects_empty_or_only_exempt_tree(
    tmp_path: Path,
    only_exempt: bool,
) -> None:
    fixture = make_good_repo(tmp_path)
    empty_docs = fixture.root / "empty-docs"
    empty_docs.mkdir()
    if only_exempt:
        exempt = empty_docs / "specs"
        exempt.mkdir()
        (exempt / "ignored.md").write_text("secret-like ignored content\n", encoding="utf-8")

    result = run_lint(fixture, docs=empty_docs)

    assert_finding(result, "E999", "no non-exempt Markdown files were scanned")
    assert "Summary: 1 error, 0 warnings, 0 files scanned" in result.stdout


def test_custom_exemption_skips_subtree_entirely(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    legacy = fixture.docs / "legacy"
    legacy.mkdir()
    (legacy / "BROKEN.md").write_text("not front matter\n", encoding="utf-8")

    result = run_lint(fixture, "--exempt", "legacy")

    assert result.returncode == 0, result.stdout + result.stderr
    assert finding_codes(result) == []
    assert "5 files scanned" in result.stdout


def test_cli_returns_usage_error_for_docs_path_outside_repo(tmp_path: Path) -> None:
    fixture = make_good_repo(tmp_path)
    outside_docs = tmp_path / "outside-docs"
    outside_docs.mkdir()

    result = run_lint(fixture, docs=outside_docs)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "docs-dir must resolve inside --repo" in result.stderr
