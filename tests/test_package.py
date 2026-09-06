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
