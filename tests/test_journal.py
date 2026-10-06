"""Append-only review journal for interrupt visibility."""

from __future__ import annotations

from pathlib import Path

from repolens.pipeline.journal import append_event, journal_path, read_events


def test_append_event_writes_jsonl_under_repolens(tmp_path: Path) -> None:
    append_event(
        tmp_path,
        "pass_started",
        role="p1",
        model="mock",
        files_count=3,
        char_budget=1000,
    )
    path = journal_path(tmp_path)
    assert path.is_file()
    rows = read_events(tmp_path)
    assert len(rows) == 1
    assert rows[0]["event"] == "pass_started"
    assert rows[0]["role"] == "p1"
    assert rows[0]["files_count"] == 3
    assert "ts" in rows[0]


def test_append_event_appends_without_truncating(tmp_path: Path) -> None:
    append_event(tmp_path, "pass_started", role="p1")
    append_event(tmp_path, "pass_completed", role="p1", duration_s=12, findings_count=2)
    rows = read_events(tmp_path)
    assert [r["event"] for r in rows] == ["pass_started", "pass_completed"]
    assert rows[1]["findings_count"] == 2


def test_read_events_skips_corrupt_lines(tmp_path: Path) -> None:
    path = journal_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"ts":"t","event":"ok"}\nNOT JSON\n{"ts":"t2","event":"ok2"}\n',
        encoding="utf-8",
    )
    rows = read_events(tmp_path)
    assert [r["event"] for r in rows] == ["ok", "ok2"]


def test_journal_path_is_under_dot_repolens(tmp_path: Path) -> None:
    assert journal_path(tmp_path) == tmp_path / ".repolens" / "journal.jsonl"


def test_read_events_empty_when_journal_missing(tmp_path: Path) -> None:
    assert read_events(tmp_path) == []


def test_summarize_chars_and_last_finished(tmp_path: Path) -> None:
    from repolens.pipeline.journal import last_finished_label, summarize_chars

    append_event(
        tmp_path,
        "pass_completed",
        role="p1",
        label="P1 Security",
        chars_in=100,
        chars_out=20,
        resumed=False,
    )
    append_event(
        tmp_path,
        "pass_completed",
        role="p2",
        label="P2 Reliability",
        chars_in=50,
        chars_out=10,
        resumed=True,
    )
    totals = summarize_chars(tmp_path)
    assert totals["chars_in"] == 150
    assert totals["chars_out"] == 30
    assert totals["pass_completed"] == 2
    assert totals["resumed"] == 1
    assert last_finished_label(tmp_path) == "P2 Reliability"


def test_read_events_skips_blank_lines(tmp_path: Path) -> None:
    path = journal_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '\n{"ts":"t","event":"ok"}\n\n',
        encoding="utf-8",
    )
    assert [r["event"] for r in read_events(tmp_path)] == ["ok"]


def test_append_event_swallows_oserror(tmp_path: Path, monkeypatch) -> None:
    path = journal_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    real_open = Path.open

    def boom(self, *args, **kwargs):
        if self == path:
            raise OSError("disk full")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", boom)
    append_event(tmp_path, "pass_started", role="p1")  # must not raise


def test_raise_aborted_records_interrupted_event(tmp_path: Path) -> None:
    from repolens.pipeline.pass_resume import raise_aborted
    from repolens.pipeline.types import ReviewAborted

    try:
        raise_aborted([], [], ["P1 Security"], root=tmp_path)
    except ReviewAborted:
        pass
    rows = read_events(tmp_path)
    assert any(r["event"] == "interrupted" for r in rows)
    interrupted = next(r for r in rows if r["event"] == "interrupted")
    assert interrupted["last_finished"] == "P1 Security"
    assert interrupted["finished"] == ["P1 Security"]
