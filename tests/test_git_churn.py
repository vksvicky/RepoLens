"""C7 git churn hotspots (path, commits, added, deleted)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repolens.git_churn import GitChurnError, collect_git_hotspots, is_safe_since


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _commit(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _git(cwd, "add", rel)
    _git(
        cwd,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=test",
        "commit",
        "-m",
        f"touch {rel}",
    )


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    return tmp_path


def test_since_allowlist() -> None:
    assert is_safe_since("6.months")
    assert is_safe_since("1.year")
    assert is_safe_since("2024-01-01")
    assert not is_safe_since("--all")
    assert not is_safe_since("6.months;id")
    assert not is_safe_since("-1 day")


def test_hotspots_rank_by_commit_count(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _commit(root, "once.py", "a = 1\n")
    _commit(root, "hot.py", "x = 1\n")
    _commit(root, "hot.py", "x = 2\n")
    rows = collect_git_hotspots(root, since="10.years")
    assert rows
    assert rows[0]["path"] == "hot.py"
    assert rows[0]["commits"] == 2
    assert rows[0]["added"] >= 1
    once = next(r for r in rows if r["path"] == "once.py")
    assert once["commits"] == 1


def test_not_a_git_repo_raises(tmp_path: Path) -> None:
    with pytest.raises(GitChurnError, match="git"):
        collect_git_hotspots(tmp_path, since="6.months")


def test_unsafe_since_raises(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _commit(root, "a.py", "1\n")
    with pytest.raises(GitChurnError, match="since"):
        collect_git_hotspots(root, since="--all")
