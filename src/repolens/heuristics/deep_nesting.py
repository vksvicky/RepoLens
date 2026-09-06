"""Indent-depth nesting heuristic (Fast Brain — line/indent only, no AST)."""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

CODE_SUFFIXES = {".swift", ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".kt"}


def _indent_depth(line: str) -> int:
    """Return indent levels from leading whitespace (spaces÷4 or tab count)."""
    if not line or not line[0].isspace():
        return 0
    # Prefer tabs when the line is tab-indented; otherwise count space groups of 4.
    if line[0] == "\t":
        i = 0
        while i < len(line) and line[i] == "\t":
            i += 1
        return i
    i = 0
    while i < len(line) and line[i] == " ":
        i += 1
    return i // 4


def _count_deep_lines(text: str, *, min_depth: int) -> tuple[int, int]:
    """Return (deep_line_count, first_deep_line_number_1based)."""
    count = 0
    first = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        if _indent_depth(raw) >= min_depth:
            count += 1
            if first == 0:
                first = lineno
    return count, first


def find_deep_nesting(
    files: list[FileEntry],
    *,
    min_depth: int = 6,
    min_lines: int = 12,
) -> list[Issue]:
    """Flag code files with many deeply indented lines (nesting smell)."""
    issues: list[Issue] = []
    for entry in files:
        if not entry.path.is_file():
            continue
        suffix = Path(entry.relative).suffix.lower()
        if suffix not in CODE_SUFFIXES:
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        deep_count, first_line = _count_deep_lines(text, min_depth=min_depth)
        if deep_count < min_lines:
            continue
        issues.append(
            Issue(
                severity=Severity.MEDIUM,
                priority="P2",
                category="heuristic.deep_nesting",
                file=entry.relative,
                line=first_line or 1,
                title=f"Deep nesting: {entry.relative} has {deep_count} deeply indented lines",
                explanation=(
                    f"Found {deep_count} non-empty lines indented to depth ≥ {min_depth} "
                    f"(threshold {min_lines} lines). Deep nesting often signals "
                    "hard-to-follow control flow or overly nested conditionals."
                ),
                recommendedFix=(
                    "Flatten control flow (early returns / guard clauses), extract "
                    "helpers, or reduce nesting with clearer structure."
                ),
                fixTiming="before launch",
                source="heuristic",
            )
        )
    return issues
