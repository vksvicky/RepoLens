"""Plain progress for a paused review: file checks done, left, and percent."""

from __future__ import annotations

from pathlib import Path

from repolens.pipeline.journal import read_events


def _files(count: int) -> str:
    n = max(0, int(count))
    return "1 file" if n == 1 else f"{n} files"


_FULL_PERCENT = 100


def file_work_line(done: int, total: int) -> str:
    """``16 of 48 file checks done (33%). 32 files still to go.``"""
    done_n = max(0, int(done))
    total_n = max(0, int(total))
    pending = max(0, total_n - done_n)
    pct = 0 if total_n == 0 else min(_FULL_PERCENT, (_FULL_PERCENT * done_n) // total_n)
    return f"{done_n} of {total_n} file checks done ({pct}%). {_files(pending)} still to go."


def pass_status_line(
    *,
    done: int,
    total: int,
    label: str,
    files: int,
    resumed: bool,
) -> str:
    work = file_work_line(done, total)
    state = "saved — skipping it" if resumed else "writing now"
    return f"{work} {label}: {_files(files)}, {state}."


def saved_pass_rerun_line(
    label: str,
    saved_files: int | None,
    current_files: int,
) -> str:
    """Why a finished pass was not reused. Empty when nothing was saved."""
    if saved_files is None:
        return ""
    if saved_files != current_files:
        return (
            f"The saved {label} was for {_files(saved_files)}. "
            f"This run has {_files(current_files)}, so that pass runs again."
        )
    return f"The saved {label} does not match these files, so it runs again."


def latest_completed_file_count(root: Path, label: str) -> int | None:
    found: int | None = None
    for row in read_events(root):
        if row.get("event") != "pass_completed" or row.get("degraded"):
            continue
        if str(row.get("label") or "") != label:
            continue
        count = row.get("files_count")
        if isinstance(count, int):
            found = count
    return found


def continue_line(root: Path) -> str | None:
    """Banner for the first run after a cancel. Later runs stay quiet."""
    events = read_events(root)
    starts = [i for i, row in enumerate(events) if row.get("event") == "review_started"]
    if not starts:
        return None
    prior = events[: starts[-1]]
    interrupted = next(
        (row for row in reversed(prior) if row.get("event") == "interrupted"),
        None,
    )
    if interrupted is None:
        return None
    interrupt_at = prior.index(interrupted)
    prior_starts = [i for i, row in enumerate(prior) if row.get("event") == "review_started"]
    # A review that already started after the cancel does not need the banner again.
    if prior_starts and prior_starts[-1] > interrupt_at:
        return None
    saved = interrupted.get("finished") or []
    names = ", ".join(str(item) for item in saved) or "none"
    return f"Continuing. Saved: {names}. A pass that was cancelled mid-write starts again."
