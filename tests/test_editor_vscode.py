"""Thin VS Code / Cursor client shells CLI (no in-process analysis, no review on save)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "editors" / "vscode"


def test_extension_manifest_palette_commands() -> None:
    pkg = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
    commands = {c["command"] for c in pkg["contributes"]["commands"]}
    assert commands >= {
        "repolens.check",
        "repolens.diff",
        "repolens.deps",
        "repolens.wouldCycle",
        "repolens.breakup",
        "repolens.previewCut",
        "repolens.duplicates",
        "repolens.ignore",
        "repolens.explain",
        "repolens.copyFullReview",
    }
    assert pkg["main"] == "./extension.js"


def test_extension_save_path_is_check_sarif_not_review() -> None:
    src = (EXT / "extension.js").read_text(encoding="utf-8")
    assert "--format" in src and "sarif" in src
    save_at = src.index("onDidSaveTextDocument")
    save_block = src[save_at : save_at + 350]
    assert "runCheck" in save_block
    assert "copyFullReview" not in save_block
    assert "graph" in src
    assert "duplicates" in src
    assert "ignore" in src
    assert "--omit-edge" in src


def test_zed_and_intellij_first_versions_exist() -> None:
    assert (ROOT / "editors" / "zed" / "README.md").is_file()
    assert (ROOT / "editors" / "intellij" / "README.md").is_file()
