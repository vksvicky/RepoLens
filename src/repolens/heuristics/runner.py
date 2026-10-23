"""Orchestrate heuristic signals into issues + hot paths (Fast Brain)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from repolens.config import NearClonesConfig
from repolens.heuristics.agent_context_hygiene import find_agent_context_hygiene
from repolens.heuristics.boolean_flags import boolean_flag_issues
from repolens.heuristics.ci_gaps import find_ci_gaps
from repolens.heuristics.deep_nesting import deep_nesting_issues
from repolens.heuristics.gitignore_secrets import find_gitignore_secret_gaps
from repolens.heuristics.large_functions import large_function_issues
from repolens.heuristics.logging_hygiene import logging_issues
from repolens.heuristics.magic_numbers import magic_number_issues
from repolens.heuristics.mega_files import (
    DEFAULT_MEGA_AND_SKIP_EXCLUDES,
    is_mega_file_excluded,
    mega_issues_for_text,
)
from repolens.heuristics.near_clones import find_near_clones
from repolens.heuristics.parameter_lists import parameter_list_issues
from repolens.heuristics.scripts_hygiene import script_credential_issues, todo_density_issues
from repolens.heuristics.siblings import find_sibling_pairs
from repolens.heuristics.standards_gaps import find_standards_gaps
from repolens.heuristics.transport_tls import transport_tls_issues
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


def _issue_key(issue: Issue) -> tuple:
    return (issue.file, issue.line, issue.category, issue.title)


def _evaluate_file_heuristics(
    entry: FileEntry,
    text: str,
    *,
    mega_file_lines: int,
    excludes: Sequence[str],
) -> list[Issue]:
    """Score one file from the string already read. The string is not retained."""
    issues = mega_issues_for_text(
        entry,
        text,
        mega_file_lines=mega_file_lines,
        exclude_globs=excludes,
    )
    if is_mega_file_excluded(entry.relative, excludes):
        return issues
    issues.extend(deep_nesting_issues(entry, text))
    issues.extend(large_function_issues(entry, text))
    issues.extend(transport_tls_issues(entry, text))
    issues.extend(script_credential_issues(entry, text))
    issues.extend(todo_density_issues(entry, text))
    issues.extend(logging_issues(entry, text))
    issues.extend(parameter_list_issues(entry, text))
    issues.extend(magic_number_issues(entry, text))
    issues.extend(boolean_flag_issues(entry, text))
    return issues


def _read_and_evaluate(
    chunk: list[FileEntry],
    *,
    mega_file_lines: int,
    excludes: Sequence[str],
) -> list[Issue]:
    issues: list[Issue] = []
    for entry in chunk:
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logging.getLogger(__name__).debug("handled expected error", exc_info=True)
            continue
        issues.extend(
            _evaluate_file_heuristics(
                entry,
                text,
                mega_file_lines=mega_file_lines,
                excludes=excludes,
            )
        )
    return issues


def _of(found: list[Issue], *categories: str) -> list[Issue]:
    wanted = set(categories)
    rows = [issue for issue in found if issue.category in wanted]
    rows.sort(key=_issue_key)
    return rows


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


@dataclass
class RunHeuristics:
    root: Path
    entries: list[FileEntry]
    mega_file_lines: int = 500
    mega_file_exclude_globs: Sequence[str] | None = None
    pack_ids: Sequence[str] | None = None
    workers: int = 1
    near_clones_config: NearClonesConfig | None = None


def run_heuristics(job: RunHeuristics) -> HeuristicResult:
    """Fast Brain heuristics — regex/line/stat only (no AST). See Phase 6.11."""
    root = job.root.resolve()
    entries = job.entries
    mega_file_lines = job.mega_file_lines
    mega_file_exclude_globs = job.mega_file_exclude_globs
    pack_ids = job.pack_ids
    workers = job.workers
    if workers <= 0:
        from repolens.heuristics.workers import resolve_fast_brain_workers

        workers = resolve_fast_brain_workers(0)
    workers = max(1, int(workers))
    near_clones_config = job.near_clones_config
    issues: list[Issue] = []
    hot_paths: list[str] = []
    excludes = (
        DEFAULT_MEGA_AND_SKIP_EXCLUDES
        if not mega_file_exclude_globs
        else tuple(dict.fromkeys((*DEFAULT_MEGA_AND_SKIP_EXCLUDES, *mega_file_exclude_globs)))
    )
    reviewable = [entry for entry in entries if not is_mega_file_excluded(entry.relative, excludes)]
    per_file = _map_entry_issues(
        entries,
        partial(_read_and_evaluate, mega_file_lines=mega_file_lines, excludes=excludes),
        workers=workers,
    )
    _absorb(issues, hot_paths, _of(per_file, "heuristic.mega_file"))
    _absorb(issues, hot_paths, find_sibling_pairs(reviewable))
    _absorb(issues, hot_paths, _of(per_file, "heuristic.deep_nesting"))
    _absorb(issues, hot_paths, _of(per_file, "heuristic.large_function"))
    issues.extend(_of(per_file, "heuristic.transport_tls"))
    clone_issues, clusters, occurrences, clone_notes = _near_clone_bundle(
        reviewable, near_clones_config
    )
    _absorb(issues, hot_paths, clone_issues)
    issues.extend(find_gitignore_secret_gaps(root, entries))
    issues.extend(_of(per_file, "heuristic.scripts_hygiene"))
    issues.extend(_of(per_file, "heuristic.todo_density"))
    issues.extend(find_ci_gaps(root, entries))
    issues.extend(find_standards_gaps(root, entries))
    issues.extend(find_agent_context_hygiene(entries))
    issues.extend(_of(
        per_file,
        "heuristic.logging_secret",
        "heuristic.swallowed_exception",
        "heuristic.logging_eager",
    ))
    issues.extend(_of(per_file, "heuristic.long_parameter_list"))
    issues.extend(_of(per_file, "heuristic.magic_number"))
    issues.extend(_of(per_file, "heuristic.boolean_flag"))
    _absorb(issues, hot_paths, _pack_issues(root, entries, pack_ids))
    return HeuristicResult(
        issues=issues,
        hot_paths=_unique_paths(hot_paths),
        near_clone_clusters=clusters,
        near_clone_occurrences=occurrences,
        near_clone_notes=clone_notes,
    )
