"""Mega-file (LOC threshold) heuristic."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.path_globs import (
    DEFAULT_REVIEW_SKIP_GLOBS,
    matches_glob,
    merge_globs,
)
from repolens.schema import Issue, Severity

DEFAULT_MEGA_FILE_EXCLUDES: tuple[str, ...] = (
    "**/*.md",
    "**/docs/**",
    "**/.superpowers/**",
    "**/xcuserdata/**",
    "**/*.xcuserstate",
    "**/*.pbxproj",
)
# Docs stay in the review. Generated trees are also omitted from the mega-file check.
DEFAULT_MEGA_AND_SKIP_EXCLUDES: tuple[str, ...] = merge_globs(
    DEFAULT_MEGA_FILE_EXCLUDES,
    DEFAULT_REVIEW_SKIP_GLOBS,
)


def count_lines(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    if not text:
        return 0
    # Count newline-terminated lines; final non-empty line without newline counts as 1.
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def is_mega_file_excluded(
    relative: str,
    exclude_globs: Sequence[str] = DEFAULT_MEGA_AND_SKIP_EXCLUDES,
) -> bool:
    return any(matches_glob(relative, pattern) for pattern in exclude_globs)


def find_mega_files(
    entries: list[FileEntry],
    *,
    mega_file_lines: int = 500,
    exclude_globs: Sequence[str] = DEFAULT_MEGA_AND_SKIP_EXCLUDES,
) -> tuple[list[Issue], list[str]]:
    issues: list[Issue] = []
    hot_paths: list[str] = []
    for entry in entries:
        if not entry.path.is_file():
            continue
        if is_mega_file_excluded(entry.relative, exclude_globs):
            continue
        lines = count_lines(entry.path)
        if lines < mega_file_lines:
            continue
        hot_paths.append(entry.relative)
        issues.append(
            Issue(
                severity=Severity.MEDIUM,
                priority="P2",
                category="heuristic.mega_file",
                file=entry.relative,
                line=1,
                title=f"Mega-file: {entry.relative} has {lines} lines",
                explanation=(
                    f"This file is {lines} lines (threshold {mega_file_lines}). "
                    "Large files are harder to review, test, and refactor safely."
                ),
                recommendedFix=(
                    "Split by responsibility (types, UI, IO, localization tables) "
                    "into smaller modules with clear boundaries."
                ),
                fixTiming="before launch",
            )
        )
    return issues, hot_paths
