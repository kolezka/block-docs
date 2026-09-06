"""Regression checks for document boundaries and evidence modes."""

from pathlib import Path

import pytest

from test_lint import finding_codes, git, make_good_repo, replace_pin, run_lint


@pytest.mark.parametrize(("opening", "closing"), [("```text", "```"), ("~~~text", "~~~~")])
def test_checks_resume_after_a_fenced_example(tmp_path: Path, opening: str, closing: str):
    fixture = make_good_repo(tmp_path)
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    with contracts.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n\n{}\n`ignored/example.py::fake()`\n{}\n\n"
            "## Real contract after the example\n\n"
            "`missing/real.py::symbol()` is an ungrounded claim. [verified]\n"
            "A prose clause — another clause.\n".format(opening, closing)
        )
    result = run_lint(fixture)
    codes = finding_codes(result)
    assert result.returncode == 1, result.stdout
    assert codes.count("E006") == 1, result.stdout
    assert codes.count("E008") == 1, result.stdout
    assert codes.count("W002") == 1, result.stdout
    assert "ignored/example.py" not in result.stdout


def test_no_git_does_not_turn_planned_spec_targets_into_existing_code(tmp_path: Path):
    fixture = make_good_repo(tmp_path)
    for page in fixture.docs.rglob("*.md"):
        replace_pin(page, fixture.pin, "spec@" + fixture.pin)
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8").replace(
        "src/service.py::enforce_rule()", "planned/worker.py::retryLimit()"
    )
    contracts.write_text(text.replace("enforcement: ", "enforcement: planned: "), encoding="utf-8")
    result = run_lint(fixture, "--no-git")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "E006" not in finding_codes(result), result.stdout
    assert "1 code citation skipped for spec pin" in result.stdout


@pytest.mark.parametrize("value", ["src/service.py::enforce_rule()", "src/service.py::enforce_rule() (runtime)"])
def test_inline_wrapped_enforcement_is_a_real_field(tmp_path: Path, value: str):
    fixture = make_good_repo(tmp_path)
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8")
    text = text.replace("enforcement: `src/service.py::enforce_rule()`", "`enforcement: " + value + "`")
    contracts.write_text(text, encoding="utf-8")
    result = run_lint(fixture)
    assert result.returncode == 0, result.stdout + result.stderr
    assert finding_codes(result) == []


def test_inline_wrapped_empty_enforcement_is_not_a_real_field(tmp_path: Path):
    fixture = make_good_repo(tmp_path)
    contracts = fixture.docs / "alpha" / "CONTRACTS.md"
    text = contracts.read_text(encoding="utf-8")
    contracts.write_text(text.replace("enforcement: `src/service.py::enforce_rule()`", "`enforcement:`"), encoding="utf-8")
    result = run_lint(fixture)
    assert result.returncode == 1, result.stdout
    assert finding_codes(result).count("E008") == 1, result.stdout


@pytest.mark.parametrize("mode", ["", "spec@"])
def test_same_commit_with_short_and_full_pins_is_consistent(tmp_path: Path, mode: str):
    fixture = make_good_repo(tmp_path)
    for page in fixture.docs.rglob("*.md"):
        replace_pin(page, fixture.pin, mode + fixture.pin)
    full_pin = git(fixture.root, "rev-parse", fixture.pin)
    replace_pin(fixture.docs / "alpha" / "README.md", mode + fixture.pin, mode + full_pin)
    result = run_lint(fixture, "--strict")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "W001" not in finding_codes(result)


def test_block_readme_must_declare_ownership(tmp_path: Path):
    fixture = make_good_repo(tmp_path)
    readme = fixture.docs / "alpha" / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(text.replace("owns: [src/service.py]\n", ""), encoding="utf-8")
    result = run_lint(fixture)
    assert result.returncode == 1, result.stdout
    assert "E001" in finding_codes(result), result.stdout
    assert "owns" in result.stdout
