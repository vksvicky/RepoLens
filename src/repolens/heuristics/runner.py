"""Orchestrate heuristic signals into issues + hot paths."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from repolens.heuristics.ci_gaps import find_ci_gaps
from repolens.heuristics.gitignore_secrets import find_gitignore_secret_gaps
from repolens.heuristics.mega_files import DEFAULT_MEGA_FILE_EXCLUDES, find_mega_files
from repolens.heuristics.scripts_hygiene import find_script_credential_hygiene, find_todo_density
from repolens.heuristics.siblings import find_sibling_pairs
from repolens.inventory import FileEntry
from repolens.schema import Issue


@dataclass
class HeuristicResult:
    issues: list[Issue] = field(default_factory=list)
    hot_paths: list[str] = field(default_factory=list)


def run_heuristics(
    root: Path,
    entries: list[FileEntry],
    *,
    mega_file_lines: int = 500,
    mega_file_exclude_globs: Sequence[str] | None = None,
    pack_ids: Sequence[str] | None = None,
) -> HeuristicResult:
    root = root.resolve()
    issues: list[Issue] = []
    hot_paths: list[str] = []

    excludes = (
        mega_file_exclude_globs
        if mega_file_exclude_globs is not None
        else DEFAULT_MEGA_FILE_EXCLUDES
    )
    mega_issues, mega_hots = find_mega_files(
        entries,
        mega_file_lines=mega_file_lines,
        exclude_globs=excludes,
    )
    issues.extend(mega_issues)
    hot_paths.extend(mega_hots)

    sibling_issues = find_sibling_pairs(entries)
    issues.extend(sibling_issues)
    for issue in sibling_issues:
        if issue.file not in hot_paths:
            hot_paths.append(issue.file)

    issues.extend(find_gitignore_secret_gaps(root, entries))
    issues.extend(find_script_credential_hygiene(entries))
    issues.extend(find_todo_density(entries))
    issues.extend(find_ci_gaps(root, entries))

    if pack_ids:
        from repolens.packs.registry import run_pack_heuristics

        pack_issues = run_pack_heuristics(root, entries, list(pack_ids))
        issues.extend(pack_issues)
        for issue in pack_issues:
            if issue.file not in hot_paths:
                hot_paths.append(issue.file)

    # Stable, de-duplicated hot paths (preserve order).
    seen: set[str] = set()
    ordered_hots: list[str] = []
    for path in hot_paths:
        if path not in seen:
            seen.add(path)
            ordered_hots.append(path)

    return HeuristicResult(issues=issues, hot_paths=ordered_hots)
