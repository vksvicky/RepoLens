"""Phase 6.3: CI triage routing decisions and caps."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from repolens.config import CiConfig, ModelConfig, RepoLensConfig, ScannersConfig
from repolens.pipeline import run_review
from repolens.schema import Issue, ScannerRun, Severity
from repolens.triage import (
    fail_on_triggered,
    infer_issue_source,
    stamp_issue_sources,
    triage_llm_plan,
)


def _issue(
    *,
    category: str = "semgrep",
    file: str = "a.py",
    line: int = 42,
    severity: Severity = Severity.HIGH,
    title: str = "bad pattern",
    source: str | None = None,
) -> Issue:
    kwargs = dict(
        severity=severity,
        priority="P1",
        category=category,
        file=file,
        line=line,
        title=title,
        explanation="x",
        impact="Known risk in production paths.",
        recommendedFix="Fix it",
        codeExample="# fix",
    )
    if source is not None:
        kwargs["source"] = source
    return Issue(**kwargs)


def test_clean_scanners_bypass_llm() -> None:
    plan = triage_llm_plan(
        [],
        available_files=["a.py", "b.py"],
        config=CiConfig(triage_routing=True),
    )
    assert plan.should_invoke_llm is False
    assert plan.llm_bypassed is True
    assert plan.pack_files == []
    assert plan.triage_hits == 0


def test_high_hit_scopes_pack_to_hit_file_not_full_tree() -> None:
    plan = triage_llm_plan(
        [_issue(file="a.py", line=42)],
        available_files=["a.py", "b.py", "c.py", "d.py"],
        config=CiConfig(triage_routing=True, max_triage_files=8),
    )
    assert plan.should_invoke_llm is True
    assert plan.llm_bypassed is False
    assert plan.pack_files == ["a.py"]
    assert "b.py" not in plan.pack_files
    assert plan.triage_hits == 1


def test_severity_below_floor_bypasses() -> None:
    plan = triage_llm_plan(
        [_issue(severity=Severity.LOW, file="a.py")],
        available_files=["a.py"],
        config=CiConfig(triage_routing=True, severity_floor="HIGH"),
    )
    assert plan.should_invoke_llm is False
    assert plan.llm_bypassed is True


def test_llm_on_clean_diff_override_allows_llm() -> None:
    plan = triage_llm_plan(
        [],
        available_files=["a.py", "b.py"],
        config=CiConfig(triage_routing=True, llm_on_clean_diff=True),
    )
    assert plan.should_invoke_llm is True
    assert plan.llm_bypassed is False
    assert plan.pack_files == ["a.py", "b.py"]


def test_triage_disabled_passes_through_full_pack() -> None:
    plan = triage_llm_plan(
        [],
        available_files=["a.py", "b.py"],
        config=CiConfig(triage_routing=False),
    )
    assert plan.should_invoke_llm is True
    assert plan.llm_bypassed is False
    assert plan.pack_files == ["a.py", "b.py"]


def test_max_triage_files_truncates_with_note() -> None:
    issues = [
        _issue(file="a.py", title="a"),
        _issue(file="b.py", title="b"),
        _issue(file="c.py", title="c"),
    ]
    plan = triage_llm_plan(
        issues,
        available_files=["a.py", "b.py", "c.py"],
        config=CiConfig(triage_routing=True, max_triage_files=2),
    )
    assert plan.should_invoke_llm is True
    assert len(plan.pack_files) == 2
    assert plan.truncated is True
    assert any("max_triage_files" in n for n in plan.notes)


def test_changed_paths_filter_ignores_unrelated_hits() -> None:
    plan = triage_llm_plan(
        [
            _issue(file="legacy.py", title="old"),
            _issue(file="pr.py", title="new"),
        ],
        available_files=["pr.py", "legacy.py"],
        changed_files=["pr.py"],
        config=CiConfig(triage_routing=True),
    )
    assert plan.pack_files == ["pr.py"]
    assert plan.triage_hits == 1


def test_infer_and_stamp_issue_sources() -> None:
    scanner = _issue(category="osv")
    heur = _issue(category="heuristic.mega_file", severity=Severity.MEDIUM)
    llm = _issue(category="sec.injection")
    stamped = stamp_issue_sources([scanner, heur, llm], default_llm=True)
    assert infer_issue_source(stamped[0]) == "scanner"
    assert infer_issue_source(stamped[1]) == "heuristic"
    assert infer_issue_source(stamped[2]) == "llm"


def test_fail_on_scanner_only_ignores_llm_findings() -> None:
    from repolens.schema import FindingReport, Summary

    report = FindingReport(
        confidence=50,
        summary=Summary(),
        issues=[
            _issue(category="sec.x", source="llm", severity=Severity.CRITICAL),
            _issue(category="semgrep", source="scanner", severity=Severity.MEDIUM),
        ],
    )
    assert fail_on_triggered(report, "HIGH", scanner_only=True) is False
    assert fail_on_triggered(report, "MEDIUM", scanner_only=True) is True
    assert fail_on_triggered(report, "HIGH", scanner_only=False) is True


def test_ci_clean_diff_does_not_call_llm(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="dummy"),
        scanners=ScannersConfig(enabled=["gitleaks"]),
        ci=CiConfig(triage_routing=True),
    )
    fake_run = ScannerRun(tool="gitleaks", status="ran", findingCount=0)
    llm_mock = MagicMock(side_effect=AssertionError("LLM must not be called"))
    with (
        patch(
            "repolens.pipeline.run.run_scanners",
            return_value=([fake_run], [], []),
        ),
        patch("repolens.pipeline.run._analyze_with_repair", llm_mock),
        patch("repolens.pipeline.run._analyze_deep_passes", llm_mock),
    ):
        result = run_review(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            out_dir=tmp_path / "r",
            scanners="auto",
            ci=True,
            deep=False,
        )
    assert result.report.llmBypassed is True
    assert result.report.llmSkipped is True
    llm_mock.assert_not_called()

    from repolens.cli.export import llm_status_label

    assert llm_status_label(result.report) == (
        "bypassed (scanners clean at triage floor)"
    )
