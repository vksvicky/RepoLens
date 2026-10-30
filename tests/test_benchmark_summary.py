"""Before/after table from two hand-written rows. No model call."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repolens.benchmark_summary import compare_rows, require_arm


def test_require_arm_matches_the_provider() -> None:
    require_arm("ollama", "local")
    require_arm("anthropic", "byok")
    require_arm(None, "ci")
    with pytest.raises(SystemExit):
        require_arm("anthropic", "local")
    with pytest.raises(SystemExit):
        require_arm("ollama", "byok")


def test_summary_is_after_over_before_and_refuses_a_zero_denominator() -> None:
    before = {
        "fixture": "tests/fixtures/benchmark",
        "arm": "local",
        "label": "before",
        "wallSeconds": 10.0,
        "promptChars": 1_000,
        "promptTokens": 100,
        "completionTokens": 20,
        "totalTokens": 0,
        "repairCalls": 0,
        "tokenSource": "ollama",
        "missing": [],
    }
    after = dict(before)
    after["label"] = "after"
    after["wallSeconds"] = 8.0
    after["totalTokens"] = 120
    text = compare_rows(before, after)
    assert "0.80" in text
    assert "missing" in text
    assert "was not reported" in text
    assert "ollama" in text
    table = text.split("\n\n", 1)[0]
    body = [line for line in table.splitlines() if line]
    assert body
    assert all(not line.startswith("|") for line in body)
    assert len({len(line) for line in body}) == 1


def test_summary_refuses_two_different_fixtures() -> None:
    left = {"fixture": "tests/fixtures/benchmark", "label": "before", "arm": "ci"}
    right = {"fixture": "other", "label": "after", "arm": "ci"}
    with pytest.raises(ValueError, match="same fixture"):
        compare_rows(left, right)


def test_summary_script_prints_the_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    payload = {
        "fixture": "tests/fixtures/benchmark",
        "arm": "local",
        "label": "before",
        "wallSeconds": 10.0,
        "promptChars": 1_000,
        "promptTokens": 100,
        "completionTokens": 20,
        "totalTokens": 120,
        "tokenSource": "ollama",
        "missing": [],
    }
    before.write_text(json.dumps(payload), encoding="utf-8")
    payload = dict(payload)
    payload["label"] = "after"
    payload["wallSeconds"] = 8.0
    after.write_text(json.dumps(payload), encoding="utf-8")
    from repolens.benchmark_cli import main

    assert main(["--summary", str(before), str(after)]) == 0
    printed = capsys.readouterr().out
    assert "0.80" in printed
    assert "ollama" in printed
