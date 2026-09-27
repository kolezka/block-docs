"""Keep the advertised distribution complete, not just valid empty manifests."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_marketplace_resolves_to_the_complete_advertised_plugin():
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    entries = [item for item in marketplace["plugins"] if item["name"] == "block-docs"]
    assert len(entries) == 1
    plugin_root = (ROOT / entries[0]["source"]).resolve()
    assert plugin_root == ROOT
    manifest = json.loads(
        (plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == entries[0]["name"]
    required = [
        "agents/block-docs-writer.md",
        "agents/block-docs-verifier.md",
        "skills/block-docs/SKILL.md",
        "skills/block-docs/references/conventions.md",
        "skills/block-docs/references/orchestration.md",
        "scripts/blockdocs_lint.py",
    ]
    for family, pages in (
        ("root", ("README", "CONVENTIONS", "GLOSSARY", "DATA-FLOW", "OWNERSHIP")),
        ("block", ("README", "CONTRACTS", "INVARIANTS", "GAPS", "OPERATIONS", "DECISIONS")),
    ):
        required.extend(
            "skills/block-docs/references/templates/{}/{}.md".format(family, page)
            for page in pages
        )
    for relative in required:
        path = plugin_root / relative
        assert path.is_file(), "Missing distribution asset: {}".format(relative)
        assert path.stat().st_size > 0, "Empty distribution asset: {}".format(relative)


VERDICTS = {"correct", "partial", "wrong", "stale", "unverifiable"}
CLASSES = {
    "OVERGENERALIZED",
    "WRONG_DETAIL",
    "POLARITY",
    "MISSING_CASE",
    "STALE",
    "UNREACHABLE",
    "CROSS_BOUNDARY_ABSENCE",
    "ENFORCEMENT_OVERSTATED",
    "INTENT_AS_FACT",
    "OTHER",
}
BLOCK_PAGES = ("README.md", "CONTRACTS.md", "INVARIANTS.md", "GAPS.md", "OPERATIONS.md")


def test_verifier_agent_cannot_write():
    text = (ROOT / "agents" / "block-docs-verifier.md").read_text(encoding="utf-8")
    front_matter = text.split("---", 2)[1]
    tools_line = [line for line in front_matter.splitlines() if line.startswith("tools:")]
    assert len(tools_line) == 1
    assert '"Read"' in tools_line[0]
    assert '"Write"' not in tools_line[0] and '"Edit"' not in tools_line[0]
    for name in CLASSES:
        assert "`{}`".format(name) in text, "verifier does not define class {}".format(name)


def test_eval_scenarios_are_well_formed():
    scenarios = sorted(path for path in (ROOT / "evals").iterdir() if path.is_dir())
    assert len(scenarios) >= 5
    for scenario in scenarios:
        expected = json.loads((scenario / "expected.json").read_text(encoding="utf-8"))
        assert set(expected) == {"section", "verdict", "class", "why"}, scenario.name
        assert expected["verdict"] in VERDICTS, scenario.name
        assert expected["class"] in CLASSES, scenario.name
        assert expected["why"].strip(), scenario.name

        blocks = [
            path
            for path in (scenario / "repo" / "docs").iterdir()
            if path.is_dir() and (path / "README.md").is_file()
        ]
        assert blocks, "{} has no docs block".format(scenario.name)
        for block in blocks:
            for page in BLOCK_PAGES:
                page_path = block / page
                assert page_path.is_file(), "{} lacks {}".format(block, page)
                assert "\nverified_against: PIN\n" in page_path.read_text(encoding="utf-8")

        page_name, _, heading = expected["section"].partition(" > ")
        headings = set()
        for block in blocks:
            page_path = block / page_name
            if page_path.is_file():
                for line in page_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("#"):
                        headings.add(line.lstrip("#").strip())
        assert heading in headings, "{} names a missing section".format(scenario.name)
        assert any((scenario / "repo" / "src").rglob("*.*")), scenario.name
