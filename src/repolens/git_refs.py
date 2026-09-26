"""Safe git ref helpers shared by ratchet and change-set scoping."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

_MERGE_BASE_CANDIDATES = ("origin/main", "origin/master", "main", "master")

# Allow common git refs / SHAs; reject option-injection and shell metacharacters.
_SAFE_GIT_REF = re.compile(r"^(?:HEAD(?:~\d+)?|[A-Za-z0-9][A-Za-z0-9._/\-^{}]*)$")


def is_safe_git_ref(ref: str) -> bool:
    """Return True when *ref* is safe to pass as a git argv token (no shell)."""
    if not ref or len(ref) > 256 or ref.startswith("-"):
        return False
    return _SAFE_GIT_REF.fullmatch(ref) is not None


def git_available(cwd: Path) -> bool:
    if shutil.which("git") is None:
        return False
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and (completed.stdout or "").strip() == "true"


def resolve_diff_base(*, cli_base: str | None, cwd: Path | None = None) -> str | None:
    """Resolve git diff base for ratchet / change-set.

    Priority: CLI ``--base`` / ``--git-diff`` → ``GITHUB_BASE_REF`` → merge-base
    heuristic → ``HEAD~1`` → None (working-tree fallback).
    """
    if cli_base:
        return cli_base if is_safe_git_ref(cli_base) else None
    gha = os.environ.get("GITHUB_BASE_REF", "").strip()
    if gha:
        candidate = gha if gha.startswith("origin/") else f"origin/{gha}"
        return candidate if is_safe_git_ref(candidate) else None

    root = cwd or Path.cwd()
    for ref in _MERGE_BASE_CANDIDATES:
        completed = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        sha = (completed.stdout or "").strip()
        if completed.returncode == 0 and sha and is_safe_git_ref(sha):
            return sha

    parent = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD~1"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if parent.returncode == 0 and (parent.stdout or "").strip():
        return "HEAD~1"
    return None
