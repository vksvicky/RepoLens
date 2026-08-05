"""Shared path filters for heuristic passes."""

from __future__ import annotations


def is_test_fixture(relative: str) -> bool:
    """True for paths under ``tests/fixtures/`` (intentional heuristic fixtures)."""
    parts = relative.replace("\\", "/").split("/")
    return len(parts) >= 2 and parts[0] == "tests" and parts[1] == "fixtures"
