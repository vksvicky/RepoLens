"""Scanners-only benchmark control. Token totals are a measured zero."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from repolens.benchmark_ci import FIXTURE_FILES, ci_control_row, run_ci_arm
from repolens.config import ModelConfig, RepoLensConfig
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run import run_review
from repolens.schema import FindingReport, Summary

FIXTURE = Path("tests/fixtures/benchmark")


def test_benchmark_fixture_is_ten_synthetic_files() -> None:
    files = sorted(path.name for path in FIXTURE.glob("*.py"))
    assert files == list(FIXTURE_FILES)
    blob = "\n".join(path.read_text(encoding="utf-8") for path in FIXTURE.glob("*.py"))
    assert "/Users/" not in blob
    assert "http://" not in blob
    assert "https://" not in blob
    assert "password" not in blob.lower()
    assert "api_key" not in blob.lower()


def test_ci_control_row_is_a_measured_zero() -> None:
    report = FindingReport(confidence=80, summary=Summary(), durationSeconds=1.5)
    row = ci_control_row(report, label="ci", fixture="tests/fixtures/benchmark")
    assert row["arm"] == "ci"
    assert row["tokenSource"] == "none"
    assert row["promptTokens"] == 0
    assert row["completionTokens"] == 0
    assert row["totalTokens"] == 0
    assert row["repairCalls"] == 0
    assert row["promptChars"] == 0
    assert row["missing"] == []
    assert row["schemaVersion"] == "1.0"


def test_ci_fixture_does_not_call_a_model(tmp_path: Path) -> None:
    fixture = tmp_path / "benchmark"
    shutil.copytree(FIXTURE, fixture)
    with patch("repolens.llm_structured.analyze_structured") as analyze:
        result = run_review(ReviewRun(
            path=fixture,
            mode="sentinel",
            config=RepoLensConfig(model=ModelConfig(provider="ollama", lock=False)),
            scanners="off",
            scanners_only=True,
            model_lock=False,
            deep=False,
            out_dir=tmp_path / "reports",
        ))
    analyze.assert_not_called()
    row = ci_control_row(result.report, label="ci", fixture=str(fixture))
    assert row["tokenSource"] == "none"
    assert row["totalTokens"] == 0


def test_ci_arm_requests_scanners_and_skips_the_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def _fake(state: ReviewRun):
        captured["state"] = state
        from types import SimpleNamespace

        return SimpleNamespace(
            report=FindingReport(confidence=80, summary=Summary(), durationSeconds=0.2)
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("repolens.pipeline.run.run_review", _fake)
    report = run_ci_arm(FIXTURE, RepoLensConfig(), Path("docs/benchmarks/reports"))
    state = captured["state"]
    assert isinstance(state, ReviewRun)
    assert state.scanners_only is True
    assert state.deep is False
    assert state.scanners == "auto"
    assert state.out_dir is not None
    assert state.out_dir.is_absolute()
    row = ci_control_row(report, label="ci", fixture=str(FIXTURE))
    assert row["totalTokens"] == 0


def test_script_ci_writes_the_control_and_model_arms_wait_for_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from repolens.benchmark_cli import main
    from repolens.config import RepoLensConfig

    def _fake(state: ReviewRun):
        from types import SimpleNamespace

        return SimpleNamespace(
            report=FindingReport(confidence=80, summary=Summary(), durationSeconds=0.4)
        )

    monkeypatch.setattr("repolens.pipeline.run.run_review", _fake)
    monkeypatch.setattr(
        "repolens.benchmark_cli.load_config",
        lambda _path: RepoLensConfig(model=ModelConfig(provider="ollama")),
    )
    destination = tmp_path / "rows"
    assert main([
        "--path", str(FIXTURE), "--arm", "ci", "--label", "ci", "--out", str(destination),
    ]) == 0
    written = (destination / "ci.json").read_text(encoding="utf-8")
    assert '"tokenSource": "none"' in written
    assert '"totalTokens": 0' in written
    with pytest.raises(SystemExit, match="row writer"):
        main(["--path", str(FIXTURE), "--arm", "local", "--label", "before"])
