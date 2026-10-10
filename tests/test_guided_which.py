"""Guided wizard tip that points at ``repolens which``."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from repolens_guided import GuidedChoices, which_tip  # noqa: E402


def _choices(**overrides: object) -> GuidedChoices:
    base: dict[str, object] = {
        "command": "review",
        "path": ".",
        "out": None,
        "scanners_only": False,
        "dry_run": False,
        "force_full": False,
        "force_changed": False,
        "full_audit": False,
        "model": None,
        "verbose": False,
        "timeout": None,
        "fmt": "md",
        "scanners": "auto",
        "fail_on": None,
        "remote": None,
        "ref": None,
    }
    base.update(overrides)
    return GuidedChoices(**base)  # type: ignore[arg-type]


def test_which_tip_matches_guided_choice() -> None:
    assert which_tip(_choices(scanners_only=True)) == "Next time: repolens which pr"
    assert which_tip(_choices(command="sentinel")) == "Next time: repolens which security"
