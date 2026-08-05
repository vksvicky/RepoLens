"""Sibling name-pair duplication candidates."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from repolens.heuristics.paths import is_test_fixture
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

# Verb-like prefixes that often mark parallel UI/tool implementations.
_PREFIX_PAIRS: tuple[tuple[str, str], ...] = (
    ("Extract", "Replace"),
    ("Create", "Delete"),
    ("Add", "Remove"),
    ("Insert", "Delete"),
    ("Open", "Close"),
    ("Start", "Stop"),
    ("Begin", "End"),
    ("Get", "Set"),
    ("Show", "Hide"),
    ("Enable", "Disable"),
)


def _stem_parts(relative: str) -> tuple[str, str, str]:
    """Return (directory, stem, suffix) for a relative path."""
    path = Path(relative)
    return path.parent.as_posix(), path.stem, path.suffix


def _pair_key(stem: str) -> list[tuple[str, str, str]]:
    """
    For stem ExtractToolView, yield (Extract, Replace, ToolView) when paired.
    Returns list of (left_prefix, right_prefix, shared_suffix).
    """
    keys: list[tuple[str, str, str]] = []
    for left, right in _PREFIX_PAIRS:
        if stem.startswith(left) and len(stem) > len(left):
            suffix = stem[len(left) :]
            if suffix and suffix[0].isupper():
                keys.append((left, right, suffix))
        if stem.startswith(right) and len(stem) > len(right):
            suffix = stem[len(right) :]
            if suffix and suffix[0].isupper():
                keys.append((left, right, suffix))
    return keys


def find_sibling_pairs(entries: list[FileEntry]) -> list[Issue]:
    # group: (dir, left, right, suffix, ext) -> {prefix: relative}
    buckets: dict[tuple[str, str, str, str, str], dict[str, str]] = defaultdict(dict)

    for entry in entries:
        if is_test_fixture(entry.relative):
            continue
        directory, stem, ext = _stem_parts(entry.relative)
        for left, right, suffix in _pair_key(stem):
            if stem.startswith(left):
                prefix = left
            elif stem.startswith(right):
                prefix = right
            else:
                continue
            key = (directory, left, right, suffix, ext)
            buckets[key][prefix] = entry.relative

    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for (directory, left, right, suffix, _ext), found in buckets.items():
        if left not in found or right not in found:
            continue
        a, b = found[left], found[right]
        pair = tuple(sorted((a, b)))
        if pair in seen:
            continue
        seen.add(pair)
        issues.append(
            Issue(
                severity=Severity.MEDIUM,
                priority="P2",
                category="heuristic.sibling_duplication",
                file=a,
                line=1,
                title=f"Sibling duplication candidate: {left}{suffix} / {right}{suffix}",
                explanation=(
                    f"Parallel names {Path(a).name} and {Path(b).name} "
                    f"in {directory or '.'} often share duplicated structure. "
                    "Confirm whether logic can be unified behind a shared abstraction."
                ),
                recommendedFix=(
                    "Extract shared behaviour into a common type/helper and keep "
                    "only the verb-specific differences in thin wrappers."
                ),
                fixTiming="before launch",
            )
        )
    return issues
