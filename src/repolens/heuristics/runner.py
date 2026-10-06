"""Orchestrate heuristic signals into issues + hot paths (Fast Brain)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from repolens.config import NearClonesConfig
from repolens.heuristics.ci_gaps import find_ci_gaps
from repolens.heuristics.deep_nesting import find_deep_nesting
from repolens.heuristics.gitignore_secrets import find_gitignore_secret_gaps
from repolens.heuristics.mega_files import (
    DEFAULT_MEGA_AND_SKIP_EXCLUDES,
    find_mega_files,
    is_mega_file_excluded,
)
from repolens.heuristics.near_clones import find_near_clones
from repolens.heuristics.scripts_hygiene import find_script_credential_hygiene, find_todo_density
from repolens.heuristics.large_functions import find_large_functions
from repolens.heuristics.siblings import find_sibling_pairs
from repolens.heuristics.transport_tls import find_transport_tls
from repolens.inventory import FileEntry
from repolens.schema import Issue


@dataclass
class HeuristicResult:
    issues: list[Issue] = field(default_factory=list)
    hot_paths: list[str] = field(default_factory=list)
    near_clone_clusters: int = 0
    near_clone_occurrences: int = 0
    near_clone_notes: list[str] = field(default_factory=list)


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


def _remember_hot_paths(hot_paths: list[str], found: list[Issue]) -> None:
    known = set(hot_paths)
    for issue in found:
        if issue.file in known:
            continue
        known.add(issue.file)
        hot_paths.append(issue.file)


def _absorb(issues: list[Issue], hot_paths: list[str], found: list[Issue]) -> None:
    issues.extend(found)
    _remember_hot_paths(hot_paths, found)


def _mega_issues(
    chunk: list[FileEntry],
    *,
    mega_file_lines: int,
    excludes: Sequence[str],
) -> list[Issue]:
    found, _hots = find_mega_files(
        chunk,
        mega_file_lines=mega_file_lines,
        exclude_globs=excludes,
    )
    return found


def _near_clone_bundle(
    entries: list[FileEntry],
    config: NearClonesConfig | None,
) -> tuple[list[Issue], int, int, list[str]]:
    cfg = config if config is not None else NearClonesConfig()
    if not cfg.enabled:
        return [], 0, 0, []
    found = find_near_clones(entries, config=cfg)
    return found.issues, found.cluster_count, found.occurrence_count, list(found.notes)


def _pack_issues(
    root: Path,
    entries: list[FileEntry],
    pack_ids: Sequence[str] | None,
) -> list[Issue]:
    if not pack_ids:
        return []
    from repolens.packs.registry import run_pack_heuristics

    return run_pack_heuristics(root, entries, list(pack_ids))


def _unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def run_heuristics(
    root: Path,
    entries: list[FileEntry],
    *,
    mega_file_lines: int = 500,
    mega_file_exclude_globs: Sequence[str] | None = None,
    pack_ids: Sequence[str] | None = None,
    workers: int = 1,
    near_clones_config: NearClonesConfig | None = None,
) -> HeuristicResult:
    """Fast Brain heuristics — regex/line/stat only (no AST). See Phase 6.11."""
    root = root.resolve()
    issues: list[Issue] = []
    hot_paths: list[str] = []
    workers = max(1, int(workers))
    excludes = (
        DEFAULT_MEGA_AND_SKIP_EXCLUDES
        if not mega_file_exclude_globs
        else tuple(
            dict.fromkeys((*DEFAULT_MEGA_AND_SKIP_EXCLUDES, *mega_file_exclude_globs))
        )
    )

    reviewable = [
        entry
        for entry in entries
        if not is_mega_file_excluded(entry.relative, excludes)
    ]
    mega = partial(
        _mega_issues, mega_file_lines=mega_file_lines, excludes=excludes
    )
    _absorb(issues, hot_paths, _map_entry_issues(entries, mega, workers=workers))
    _absorb(issues, hot_paths, find_sibling_pairs(reviewable))
    _absorb(
        issues,
        hot_paths,
        _map_entry_issues(reviewable, find_deep_nesting, workers=workers),
    )
    _absorb(
        issues,
        hot_paths,
        _map_entry_issues(reviewable, find_large_functions, workers=workers),
    )
    issues.extend(
        _map_entry_issues(reviewable, find_transport_tls, workers=workers)
    )
    clone_issues, clusters, occurrences, clone_notes = _near_clone_bundle(
        reviewable, near_clones_config
    )
    _absorb(issues, hot_paths, clone_issues)
    issues.extend(find_gitignore_secret_gaps(root, entries))
    issues.extend(
        _map_entry_issues(
            reviewable, find_script_credential_hygiene, workers=workers
        )
    )
    issues.extend(
        _map_entry_issues(reviewable, find_todo_density, workers=workers)
    )
    issues.extend(find_ci_gaps(root, entries))
    _absorb(issues, hot_paths, _pack_issues(root, entries, pack_ids))
    return HeuristicResult(
        issues=issues,
        hot_paths=_unique_paths(hot_paths),
        near_clone_clusters=clusters,
        near_clone_occurrences=occurrences,
        near_clone_notes=clone_notes,
    )
