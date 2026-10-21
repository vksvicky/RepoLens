"""Mega-file (LOC threshold) heuristic."""

from __future__ import annotations

import logging
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
    "**/plugin_locks/**",
    "**/*-lock.json",
    "**/*.lock",
    "scripts/generate_learn_file_notes.py",
)
# Docs stay in the review. Generated trees are also omitted from the mega-file check.
DEFAULT_MEGA_AND_SKIP_EXCLUDES: tuple[str, ...] = merge_globs(
    DEFAULT_MEGA_FILE_EXCLUDES,
    DEFAULT_REVIEW_SKIP_GLOBS,
)


def line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def count_lines(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return 0
    return line_count(text)


def is_mega_file_excluded(
    relative: str,
    exclude_globs: Sequence[str] = DEFAULT_MEGA_AND_SKIP_EXCLUDES,
) -> bool:
    return any(matches_glob(relative, pattern) for pattern in exclude_globs)


def mega_issues_for_text(
    entry: FileEntry,
    text: str,
    *,
    mega_file_lines: int = 500,
    exclude_globs: Sequence[str] = DEFAULT_MEGA_AND_SKIP_EXCLUDES,
) -> list[Issue]:
    if is_mega_file_excluded(entry.relative, exclude_globs):
        return []
    lines = line_count(text)
    if lines < mega_file_lines:
        return []
    return [
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
    ]


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
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logging.getLogger(__name__).debug("handled expected error", exc_info=True)
            continue
        found = mega_issues_for_text(
            entry,
            text,
            mega_file_lines=mega_file_lines,
            exclude_globs=exclude_globs,
        )
        issues.extend(found)
        hot_paths.extend(issue.file for issue in found)
    return issues, hot_paths
