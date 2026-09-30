"""Git change-set path listing for Slow Brain ``--git-diff`` (#16)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

from repolens.git_refs import git_available, is_safe_git_ref
from repolens.inventory import FileEntry
from repolens.schema import Issue

# Cap listed paths in reports / provenance.
CHANGESET_PATH_LIST_CAP = 40


def list_git_changed_paths(
    root: Path,
    base: str | None,
    *,
    include_dirty: bool = True,
) -> list[str]:
    """Return normalised repo-relative paths changed vs *base* (and dirty tree).

    When *base* is set, uses ``git diff --name-only {base}...HEAD``.
    When *include_dirty*, also unions staged and unstaged worktree paths.
    """
    if not git_available(root):
        return []
    if base is not None and not is_safe_git_ref(base):
        return []

    collected: list[str] = []
    seen: set[str] = set()

    def _add_from_stdout(stdout: str) -> None:
        for line in (stdout or "").splitlines():
            rel = line.strip().replace("\\", "/")
            if not rel or rel in seen:
                continue
            seen.add(rel)
            collected.append(rel)

    if base is not None:
        completed = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            _add_from_stdout(completed.stdout)

    if include_dirty:
        for argv in (
            ["git", "diff", "--name-only", "--cached"],
            ["git", "diff", "--name-only"],
        ):
            completed = subprocess.run(
                argv,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode == 0:
                _add_from_stdout(completed.stdout)

    return collected


def filter_entries_to_changeset(
    entries: Sequence[FileEntry],
    changed_paths: Iterable[str],
) -> list[FileEntry]:
    """Keep inventory entries whose relative path is in the change-set (order preserved)."""
    wanted = {p.replace("\\", "/") for p in changed_paths}
    if not wanted:
        return []
    return [e for e in entries if e.relative.replace("\\", "/") in wanted]


def cap_changeset_paths(paths: Sequence[str], *, limit: int = CHANGESET_PATH_LIST_CAP) -> list[str]:
    return list(paths[:limit])


def tag_findings_for_changeset(issues: list[Issue], changed_paths: Iterable[str]) -> None:
    """Mark each finding as touched by the diff or already in the tree.

    File-level only. A review that never calls this leaves ``introducedInDiff`` unset.
    """
    changed = {path.removeprefix("./").replace("\\", "/") for path in changed_paths}
    for issue in issues:
        issue.introducedInDiff = issue.file.removeprefix("./").replace("\\", "/") in changed
