"""Thin VS Code / Cursor client shells CLI (no in-process analysis, no review on save)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "editors" / "vscode"


def test_extension_manifest_check_command() -> None:
    pkg = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
    commands = {c["command"] for c in pkg["contributes"]["commands"]}
    assert "repolens.check" in commands
    assert pkg["main"] == "./extension.js"


def test_extension_save_path_is_check_sarif_not_review() -> None:
    src = (EXT / "extension.js").read_text(encoding="utf-8")
    assert "check" in src
    assert "--format" in src
    assert "sarif" in src
    assert "--deep" not in src
    assert "review" not in src.lower()
