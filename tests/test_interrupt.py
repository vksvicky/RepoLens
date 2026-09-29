"""The first Ctrl+C unwinds. The second one leaves immediately."""

from __future__ import annotations

import signal

import pytest

from repolens.pipeline.interrupt import InterruptGuard
from repolens.pipeline.pass_resume import note_timed_out_passes, raise_aborted
from repolens.pipeline.types import ReviewAborted
from repolens.schema import FindingReport, Summary


def test_partial_report_names_finished_passes_and_leaves_the_original(tmp_path) -> None:
    from datetime import UTC, datetime

    from repolens.pipeline.pass_resume import write_partial_report

    report = FindingReport(confidence=0, summary=Summary(), issues=[])
    when = datetime(2026, 9, 29, tzinfo=UTC)
    write_partial_report(
        report,
        tmp_path,
        fmt="both",
        finished_labels=["P1 Security", "P2 Reliability"],
        mode="review",
        when=when,
    )
    assert report.durabilityGaps == []
    text = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")
    assert "Finished passes are kept: P1 Security, P2 Reliability." in text


def test_second_ctrl_c_exits_immediately() -> None:
    guard = InterruptGuard()
    with pytest.raises(KeyboardInterrupt):
        guard.handle(signal.SIGINT, None)
    with pytest.raises(SystemExit) as caught:
        guard.handle(signal.SIGINT, None)
    assert caught.value.code == 1


def test_interrupt_guard_restores_the_previous_handler() -> None:
    previous = signal.getsignal(signal.SIGINT)
    with InterruptGuard():
        assert signal.getsignal(signal.SIGINT) != previous
    assert signal.getsignal(signal.SIGINT) == previous


def test_abort_names_the_passes_that_finished() -> None:
    with pytest.raises(ReviewAborted) as caught:
        raise_aborted([], [], ["P1 Security", "P2 Reliability"])
    text = caught.value.report.durabilityGaps[0]
    assert text == (
        "Aborted by user. Finished passes are kept: P1 Security, P2 Reliability."
    )


def test_timed_out_pass_names_the_passes_that_finished() -> None:
    report = FindingReport(confidence=0, summary=Summary(), issues=[])
    noted = note_timed_out_passes(
        report,
        ["P3 Architecture"],
        ["P1 Security", "P2 Reliability"],
    )
    assert noted.durabilityGaps == [
        "The P3 Architecture pass timed out. "
        "This report includes the passes that finished "
        "(P1 Security, P2 Reliability). "
        "Re-run when the model is free. Finished passes are kept."
    ]
