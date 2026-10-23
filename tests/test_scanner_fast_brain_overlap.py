"""Scanners and Fast Brain overlap. The test proves the scanner is still in flight."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from repolens.config import RepoLensConfig
from repolens.pipeline import ReviewRun, run_review
from repolens.report import _markdown_scanners
from repolens.report_blocks import format_scanner_times
from repolens.scanners.base import ScannerResult
from repolens.scanners.runner import run_scanners
from repolens.schema import FindingReport, ScannerRun, Summary


def test_ran_tool_records_duration_and_a_skip_omits_it(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter((0.0, 1.24))
    monkeypatch.setattr("repolens.scanners.runner.time.monotonic", lambda: next(ticks))

    def _one(tool: str, _root: Path):
        run = ScannerRun(tool=tool, status="ran", findingCount=0)
        return tool, ScannerResult(run=run), None

    monkeypatch.setattr("repolens.scanners.runner._run_one", _one)
    runs, _issues, _gaps = run_scanners(Path("."), ["gitleaks"])
    assert runs[0].durationSeconds == 1.2
    skipped = [ScannerRun(tool="semgrep", status="skipped"), *runs]
    line = format_scanner_times(skipped)
    assert line == "Scanners: gitleaks 1.2s"
    assert "semgrep" not in line


def test_report_names_each_scanner_duration() -> None:
    report = FindingReport(
        confidence=1,
        summary=Summary(),
        issues=[],
        scannerRuns=[
            ScannerRun(tool="semgrep", status="ran", durationSeconds=1.2),
            ScannerRun(tool="gitleaks", status="ran", durationSeconds=0.4),
            ScannerRun(tool="trivy", status="skipped"),
        ],
    )
    text = "\n".join(_markdown_scanners(report))
    assert "Scanners: semgrep 1.2s · gitleaks 0.4s" in text
    assert "trivy" in text
    assert "trivy 0.0s" not in text


def test_fast_brain_starts_while_the_scanner_call_is_in_flight(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    order: list[str] = []
    scanner_entered = threading.Event()
    fast_started = threading.Event()

    def fake_scanners(_root: Path, _tools: list[str]):
        order.append("scanner-start")
        scanner_entered.set()
        assert fast_started.wait(2)
        order.append("scanner-end")
        run = ScannerRun(tool="gitleaks", status="ran", durationSeconds=1.2)
        return [run], [], []

    def fake_fast(state) -> None:
        assert scanner_entered.wait(2)
        order.append("fast-start")
        state.heur_issues = []
        state.fast_brain_seconds = 0.1
        fast_started.set()
        order.append("fast-end")

    def fake_supply(state) -> None:
        assert "scanner-end" in order
        order.append("supply")
        state.supply_chain = None

    def fake_fallback(state) -> None:
        assert "fast-end" in order
        assert "supply" in order
        state.non_llm_issues = []
        order.append("fallback")

    with (
        patch("repolens.pipeline.run_collect.run_scanners", fake_scanners),
        patch("repolens.pipeline.run_collect._run_fast_brain_phase", fake_fast),
        patch("repolens.pipeline.run_collect._collect_supply_chain", fake_supply),
        patch("repolens.pipeline.run_route._apply_provider_fallback", fake_fallback),
    ):
        run_review(ReviewRun(
            path=tmp_path,
            mode="sentinel",
            config=RepoLensConfig(),
            scanners="gitleaks",
            scanners_only=True,
            model_lock=False,
            out_dir=tmp_path / "reports",
        ))
    assert order.index("scanner-start") < order.index("fast-start") < order.index("scanner-end")
    assert order.index("scanner-end") < order.index("supply") < order.index("fallback")
