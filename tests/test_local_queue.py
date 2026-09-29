"""Ticket order is numeric, dead holders are dropped, and the poll sleep jitters."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from repolens.llm.local_queue import head_ticket, poll_delay, take_ticket, ticket_seq


def test_ticket_seq_parses_the_integer_prefix() -> None:
    assert ticket_seq(Path("9_12.json")) == 9
    assert ticket_seq(Path("10_12.json")) == 10


def test_head_ticket_is_the_lowest_integer(tmp_path: Path) -> None:
    pid = os.getpid()
    (tmp_path / "10_1.json").write_text(
        json.dumps({"pid": pid, "repo": "B"}), encoding="utf-8"
    )
    (tmp_path / "9_1.json").write_text(
        json.dumps({"pid": pid, "repo": "A"}), encoding="utf-8"
    )
    head = head_ticket(tmp_path)
    assert head is not None
    assert head.name == "9_1.json"


def test_take_ticket_increments_under_the_seq_file(tmp_path: Path) -> None:
    pid = os.getpid()
    first = take_ticket(tmp_path, {"repo": "A", "pass": "P1", "pid": pid})
    second = take_ticket(tmp_path, {"repo": "B", "pass": "P2", "pid": pid})
    assert ticket_seq(first) == 1
    assert ticket_seq(second) == 2
    assert head_ticket(tmp_path) == first


def test_dead_ticket_is_removed(tmp_path: Path) -> None:
    (tmp_path / "1_1.json").write_text(
        json.dumps({"pid": 2**30, "repo": "Ghost", "pass": "P1"}),
        encoding="utf-8",
    )
    live = take_ticket(tmp_path, {"repo": "RepoLens", "pass": "P2", "pid": 0})
    payload = json.loads(live.read_text(encoding="utf-8"))
    payload["pid"] = os.getpid()
    live.write_text(json.dumps(payload), encoding="utf-8")
    head = head_ticket(tmp_path)
    assert head == live
    assert not (tmp_path / "1_1.json").exists()


def test_poll_delay_stays_inside_the_jitter_window() -> None:
    assert poll_delay(jitter=lambda: -0.2) == pytest.approx(1.8)
    assert poll_delay(jitter=lambda: 0.2) == pytest.approx(2.2)
    assert poll_delay(base=0.0, jitter=lambda: 0.0) == pytest.approx(0.05)
