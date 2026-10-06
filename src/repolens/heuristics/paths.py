"""Shared path filters for heuristic passes."""

from __future__ import annotations

from fnmatch import fnmatch


def is_test_fixture(relative: str) -> bool:
    """True for paths under ``tests/fixtures/`` (intentional heuristic fixtures)."""
    parts = relative.replace("\\", "/").split("/")
    return len(parts) >= 2 and parts[0] == "tests" and parts[1] == "fixtures"


def is_test_source(relative: str) -> bool:
    """True for test trees and ``*_test`` / ``*.test`` / ``*.spec`` filenames."""
    posix = relative.replace("\\", "/")
    parts = posix.split("/")
    name = parts[-1]
    if any(fnmatch(part, "test*") for part in parts[:-1]):
        return True
    if fnmatch(name, "*_test.*") or fnmatch(name, "*.test.*") or fnmatch(name, "*.spec.*"):
        return True
    return False
