"""Per-pass timing splits queue, first token, and generation. No model is called."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.config import DeepConfig
from repolens.pipeline.journal import append_event
from repolens.pipeline.pass_timing import (
    StreamClock,
    live_pass_timing,
    resumed_pass_timing,
    with_first_token_sample,
)
from repolens.report_sections import _provenance_identity_lines
from repolens.schema import PassTiming, ProvenanceBlock


def test_chars_per_pass_stays_at_the_frozen_budget() -> None:
    assert DeepConfig().chars_per_pass == 100_000


def test_live_row_splits_first_token_from_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter((0.0, 1.5, 4.0))
    monkeypatch.setattr(
        "repolens.pipeline.pass_timing.time.perf_counter",
        lambda: next(ticks),
    )
    clock = StreamClock()
    clock.start()
    prompt = "prompt-body"

    def complete(on_chunk):
        on_chunk("abc")
        on_chunk("de")
        return "abcde"

    raw = complete(clock.note_chunk)
    clock.finish()
    row = live_pass_timing(
        "p1",
        queue_wait_seconds=0.4,
        prompt_chars=len(prompt),
        raw_text=raw,
        clock=clock,
    )
    assert row.outcome == "live"
    assert row.timeToFirstTokenSeconds == 1.5
    assert row.generationSeconds == 2.5
    assert row.promptChars == len(prompt)
    assert row.outputChars == 5
    assert row.charsPerSecond == 2.0
    assert row.queueWaitSeconds == 0.4
    assert row.tokenCount is None


def test_resumed_row_leaves_generation_fields_empty() -> None:
    row = resumed_pass_timing("p2")
    assert row.outcome == "resumed"
    assert row.timeToFirstTokenSeconds is None
    assert row.generationSeconds is None
    assert row.promptChars is None
    assert row.outputChars is None
    assert row.charsPerSecond is None
    assert row.queueWaitSeconds is None
    assert row.tokenCount is None


def test_provenance_prints_live_and_resumed_without_fake_zeros() -> None:
    live = PassTiming(
        passName="p1",
        outcome="live",
        queueWaitSeconds=0.0,
        timeToFirstTokenSeconds=1.5,
        generationSeconds=2.5,
        promptChars=12,
        outputChars=5,
        charsPerSecond=2.0,
    )
    resumed = resumed_pass_timing("p3")
    lines = _provenance_identity_lines(
        ProvenanceBlock(passTimings=[live, resumed])
    )
    text = "\n".join(lines)
    assert "Pass p1" in text
    assert "first token 1.5s" in text
    assert "generation 2.5s" in text
    assert "Pass p3" in text
    assert "resumed" in text
    assert "first token 0.0s" not in text
    assert "generation 0.0s" not in text


def test_plan_uses_the_last_first_token_for_the_same_model(tmp_path: Path) -> None:
    append_event(
        tmp_path,
        "pass_completed",
        model="qwen2.5-coder:32b",
        time_to_first_token_seconds=12.0,
        resumed=False,
    )
    append_event(
        tmp_path,
        "pass_completed",
        model="qwen2.5-coder:32b",
        time_to_first_token_seconds=8.0,
        resumed=False,
    )
    append_event(
        tmp_path,
        "pass_completed",
        model="other-model",
        time_to_first_token_seconds=99.0,
        resumed=False,
    )
    line = with_first_token_sample(
        tmp_path,
        "qwen2.5-coder:32b",
        "Slow Brain estimate: coarse",
        passes=3,
    )
    assert "Slow Brain estimate: coarse" in line
    assert "8.0s" in line
    assert "3 pass" in line
    assert "24.0s" in line
    assert "99.0s" not in line


def test_plan_says_when_this_tree_has_no_sample(tmp_path: Path) -> None:
    line = with_first_token_sample(
        tmp_path,
        "qwen2.5-coder:32b",
        "Slow Brain estimate: coarse",
        passes=2,
    )
    assert line.startswith("Slow Brain estimate: coarse")
    assert "No first-token sample" in line
