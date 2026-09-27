"""Runs the linter --strict against every evals/*/repo fixture, after
substituting the `PIN` placeholder with a real commit SHA. This locks in
that the block-docs-writer eval fixtures stay structurally clean; it must
never edit anything under evals/.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

import pytest

from test_lint import FixtureRepo, commit_all, finding_codes, git, run_lint


EVALS_ROOT = Path(__file__).resolve().parents[1] / "evals"


def _eval_repo_dirs() -> List[Path]:
    return sorted(EVALS_ROOT.glob("*/repo"))


@pytest.mark.parametrize(
    "repo_dir",
    _eval_repo_dirs(),
    ids=lambda path: path.parent.name,
)
def test_eval_scenario_is_strict_clean(tmp_path: Path, repo_dir: Path) -> None:
    work = tmp_path / "repo"
    shutil.copytree(repo_dir, work)

    git(work, "init", "-q", "-b", "main")
    git(work, "config", "user.name", "Block Docs Evals")
    git(work, "config", "user.email", "block-docs-evals@example.invalid")
    pin = commit_all(work, "eval fixture")

    docs = work / "docs"
    for page in docs.rglob("*.md"):
        text = page.read_text(encoding="utf-8")
        if "verified_against: PIN" in text:
            page.write_text(
                text.replace("verified_against: PIN", "verified_against: " + pin),
                encoding="utf-8",
            )
    commit_all(work, "fill in pin")

    fixture = FixtureRepo(root=work, docs=docs, pin=pin)
    result = run_lint(fixture, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr
    assert finding_codes(result) == [], result.stdout
