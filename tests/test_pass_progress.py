"""File-check progress and pause/continue copy."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.pipeline.journal import append_event
from repolens.pipeline.pass_progress import (
    continue_line,
    file_work_line,
    pass_status_line,
    saved_pass_rerun_line,
)
from repolens.progress import LlmGenerateProgress


def test_file_work_line_boundaries() -> None:
    assert file_work_line(0, 0) == "0 of 0 file checks done (0%). 0 files still to go."
    assert file_work_line(0, 48) == "0 of 48 file checks done (0%). 48 files still to go."
    assert file_work_line(16, 48) == "16 of 48 file checks done (33%). 32 files still to go."
    assert file_work_line(1, 3) == "1 of 3 file checks done (33%). 2 files still to go."
    assert file_work_line(2, 3) == "2 of 3 file checks done (66%). 1 file still to go."
    assert file_work_line(3, 3) == "3 of 3 file checks done (100%). 0 files still to go."
    assert file_work_line(9, 3) == "9 of 3 file checks done (100%). 0 files still to go."
    assert file_work_line(-1, 4) == "0 of 4 file checks done (0%). 4 files still to go."


def test_pass_status_line_names_saved_and_live_work() -> None:
    saved = pass_status_line(
        done=16, total=48, label="P1 Security", files=16, resumed=True
    )
    assert "16 of 48" in saved
    assert "33%" in saved
    assert "P1 Security: 16 files, saved — skipping it." in saved
    live = pass_status_line(
        done=16, total=48, label="P2 Reliability", files=16, resumed=False
    )
    assert "P2 Reliability: 16 files, writing now." in live


def test_saved_pass_rerun_line_distinguishes_count_and_content() -> None:
    assert saved_pass_rerun_line("P1 Security", None, 16) == ""
    changed_count = saved_pass_rerun_line("P1 Security", 16, 23)
    assert "16 files" in changed_count
    assert "23 files" in changed_count
    assert "runs again" in changed_count
    changed_bytes = saved_pass_rerun_line("P1 Security", 16, 16)
    assert "does not match these files" in changed_bytes
    assert "runs again" in changed_bytes
    one = saved_pass_rerun_line("P1 Security", 1, 2)
    assert "1 file" in one
    assert "2 files" in one


def test_continue_line_names_the_saved_pass_after_cancel(tmp_path: Path) -> None:
    assert continue_line(tmp_path) is None
    append_event(tmp_path, "review_started", run_id="old")
    append_event(
        tmp_path,
        "interrupted",
        finished=["P1 Security"],
        last_finished="P1 Security",
    )
    append_event(tmp_path, "review_started", run_id="new")
    text = continue_line(tmp_path)
    assert text is not None
    assert "P1 Security" in text
    assert "mid-write" in text


def test_continue_line_ignores_an_older_cancel_once_a_run_finished(tmp_path: Path) -> None:
    append_event(tmp_path, "review_started", run_id="old")
    append_event(tmp_path, "interrupted", finished=["P1 Security"])
    append_event(tmp_path, "review_started", run_id="done")
    append_event(tmp_path, "pass_completed", label="P3 Architecture", degraded=False)
    append_event(tmp_path, "review_started", run_id="new")
    assert continue_line(tmp_path) is None


@pytest.mark.parametrize("done", [0, 16])
def test_summary_leads_with_file_checks(done: int) -> None:
    gen = LlmGenerateProgress()
    gen.file_work = file_work_line(done, 48)
    assert gen.summary().startswith(file_work_line(done, 48))
    gen.note_delta("token")
    assert "file checks" in gen.summary()
    assert "characters" in gen.summary()
