"""Git churn table for ``repolens hotspots`` (C7)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from repolens.git_refs import git_available

_SINCE = re.compile(
    r"^(?:\d+\.(?:day|days|week|weeks|month|months|year|years)|\d{4}-\d{2}-\d{2})$"
)


class GitChurnError(ValueError):
    """Unsafe --since, missing git, or git log failure."""


def is_safe_since(value: str) -> bool:
    text = (value or "").strip()
    if not text or len(text) > 32 or text.startswith("-"):
        return False
    return _SINCE.fullmatch(text) is not None


def collect_git_hotspots(
    root: Path,
    *,
    since: str,
    limit: int = 50,
) -> list[dict[str, int | str]]:
    """Aggregate commits / lines added / lines deleted per path."""
    if not is_safe_since(since):
        raise GitChurnError(f"unsafe since: {since!r}")
    if not git_available(root):
        raise GitChurnError("not a git repository")
    completed = subprocess.run(
        ["git", "log", f"--since={since}", "--pretty=format:%H", "--numstat"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "git log failed").strip()
        raise GitChurnError(err[:300])

    per_path: dict[str, dict] = {}
    current_sha = ""
    for raw in (completed.stdout or "").splitlines():
        line = raw.strip("\n")
        if not line.strip():
            current_sha = ""
            continue
        if "\t" not in line:
            current_sha = line.strip()
            continue
        parts = line.split("\t")
        if len(parts) < 3 or not current_sha:
            continue
        added_s, deleted_s, path = parts[0], parts[1], "\t".join(parts[2:])
        if added_s == "-" or deleted_s == "-":
            continue
        try:
            added = int(added_s)
            deleted = int(deleted_s)
        except ValueError:
            continue
        rec = per_path.setdefault(
            path,
            {"path": path, "commits": 0, "added": 0, "deleted": 0, "_shas": set()},
        )
        rec["_shas"].add(current_sha)
        rec["added"] += added
        rec["deleted"] += deleted

    rows: list[dict[str, int | str]] = []
    for rec in per_path.values():
        shas = rec.pop("_shas")
        rec["commits"] = len(shas)
        rows.append(rec)
    rows.sort(
        key=lambda r: (-int(r["commits"]), -(int(r["added"]) + int(r["deleted"])), str(r["path"]))
    )
    cap = max(1, int(limit))
    return rows[:cap]
