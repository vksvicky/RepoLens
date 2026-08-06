"""Orchestrate heuristic signals into issues + hot paths (Fast Brain)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _chunked(entries: list[FileEntry], n_chunks: int) -> list[list[FileEntry]]:
    if not entries:
        return []
    n_chunks = max(1, min(n_chunks, len(entries)))
    size = (len(entries) + n_chunks - 1) // n_chunks
    return [entries[i : i + size] for i in range(0, len(entries), size)]


def _map_entry_issues(
    entries: list[FileEntry],
    fn: Callable[[list[FileEntry]], list[Issue]],
    *,
    workers: int,
) -> list[Issue]:
    """Run an entry-list heuristic over chunks (I/O-bound → threads)."""
    if workers <= 1 or len(entries) < 32:
        return fn(entries)
    chunks = _chunked(entries, workers)
    issues: list[Issue] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(chunks))) as pool:
        futures = [pool.submit(fn, chunk) for chunk in chunks]
        for fut in as_completed(futures):
            issues.extend(fut.result())
    # Deterministic order for tests / stableIds
    issues.sort(key=lambda i: (i.file, i.line, i.category, i.title))
    return issues


def run_heuristics(
    root: Path,
    entries: list[FileEntry],
    *,
    mega_file_lines: int = 500,
    mega_file_exclude_globs: Sequence[str] | None = None,
    pack_ids: Sequence[str] | None = None,
    workers: int = 1,
) -> HeuristicResult:
    """Fast Brain heuristics — regex/line/stat only (no AST). See Phase 6.11."""
    root = root.resolve()
    issues: list[Issue] = []
    hot_paths: list[str] = []
    workers = max(1, int(workers))

    excludes = (
        mega_file_exclude_globs
        if mega_file_exclude_globs is not None
        else DEFAULT_MEGA_FILE_EXCLUDES
    )

    def _mega(chunk: list[FileEntry]) -> list[Issue]:
        found, _hots = find_mega_files(
            chunk,
            mega_file_lines=mega_file_lines,
            exclude_globs=excludes,
        )
        return found

    mega_issues = _map_entry_issues(entries, _mega, workers=workers)
    issues.extend(mega_issues)
    for issue in mega_issues:
        if issue.file not in hot_paths:
            hot_paths.append(issue.file)

    # Path-structure only — keep single-threaded over full list.
    sibling_issues = find_sibling_pairs(entries)
    issues.extend(sibling_issues)
    for issue in sibling_issues:
        if issue.file not in hot_paths:
            hot_paths.append(issue.file)

    issues.extend(find_gitignore_secret_gaps(root, entries))
    issues.extend(
        _map_entry_issues(entries, find_script_credential_hygiene, workers=workers)
    )
    issues.extend(_map_entry_issues(entries, find_todo_density, workers=workers))
    issues.extend(find_ci_gaps(root, entries))

    if pack_ids:
        from repolens.packs.registry import run_pack_heuristics

        pack_issues = run_pack_heuristics(root, entries, list(pack_ids))
        issues.extend(pack_issues)
        for issue in pack_issues:
            if issue.file not in hot_paths:
                hot_paths.append(issue.file)

    seen: set[str] = set()
    ordered_hots: list[str] = []
    for path in hot_paths:
        if path not in seen:
            seen.add(path)
            ordered_hots.append(path)

    return HeuristicResult(issues=issues, hot_paths=ordered_hots)
