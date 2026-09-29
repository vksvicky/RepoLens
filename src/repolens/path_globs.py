"""Repo-relative glob skips shared by inventory and Fast Brain."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

# Generated trees that are not product source. Projects add more in
# [deep] skip_paths. These always apply.
DEFAULT_REVIEW_SKIP_GLOBS: tuple[str, ...] = (
    "**/bin/**",
    "**/gen/**",
    "**/test_output/**",
    "**/out/**",
    "**/*.mcgen",
)


def matches_glob(relative: str, pattern: str) -> bool:
    """Match a repo-relative path against a glob (``**/dir/**`` included)."""
    rel = relative.replace("\\", "/")
    path = PurePosixPath(rel)
    if path.match(pattern):
        return True
    if pattern.startswith("**/") and pattern.endswith("/**"):
        dirname = pattern[3:-3]
        if dirname and dirname in path.parts:
            return True
    return False


def is_skipped_path(relative: str, globs: Sequence[str]) -> bool:
    return any(matches_glob(relative, pattern) for pattern in globs)


def merge_globs(*groups: Sequence[str]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for pattern in group:
            if pattern not in merged:
                merged.append(pattern)
    return tuple(merged)
