"""Last successful LLM snapshot save / load / reuse."""

from __future__ import annotations

from pathlib import Path

from repolens.last_llm import (
    bootstrap_from_out_dir,
    load_last_llm_report,
    merge_reused_report,
    save_last_llm_report,
)
from repolens.learning.store import ProjectStore
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(title: str = "Hardcoded secret", sev: Severity = Severity.HIGH) -> Issue:
    return Issue(
        severity=sev,
        priority="P1",
        category="secrets",
        file="a.py",
        line=1,
        title=title,
        explanation="key in source",
        impact="leak",
        recommendedFix="use env",
        codeExample="os.environ['KEY']",
    )


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(high=1),
        issues=[_issue()],
        llmCompleted=True,
    )
    with ProjectStore(tmp_path) as store:
        save_last_llm_report(store, report, model="qwen:32b", mode="review")
        loaded = load_last_llm_report(store)
    assert loaded is not None
    prior, saved_at, model = loaded
    assert prior.issues[0].title == "Hardcoded secret"
    assert model == "qwen:32b"
    assert saved_at


def test_save_ignores_non_completed(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=55,
        summary=Summary(),
        issues=[],
        llmSkipped=True,
        llmCompleted=False,
    )
    with ProjectStore(tmp_path) as store:
        save_last_llm_report(store, report, model="x", mode="review")
        assert load_last_llm_report(store) is None


def test_merge_reused_keeps_prior_and_adds_scanner() -> None:
    prior = FindingReport(
        confidence=80,
        summary=Summary(high=1),
        issues=[_issue()],
        llmCompleted=True,
    )
    scanner = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="secrets",
        file="b.py",
        line=2,
        title="New scanner hit",
        explanation="scanner",
        recommendedFix="fix",
    )
    out = merge_reused_report(
        prior,
        scanner_issues=[scanner],
        scanner_runs=[],
        scanner_gaps=[],
        saved_at="2026-08-05T12:00:00+00:00",
        model="qwen:32b",
    )
    assert out.llmReusedFrom == "2026-08-05T12:00:00+00:00 · qwen:32b"
    assert out.confidence == 75
    assert len(out.issues) == 2
    assert out.llmSkipped is True
    assert out.llmCompleted is False


def test_bootstrap_picks_newest_completed(tmp_path: Path) -> None:
    out = tmp_path / "reports"
    out.mkdir()
    old = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[_issue(title="Old")],
        llmCompleted=True,
    )
    new = FindingReport(
        confidence=90,
        summary=Summary(),
        issues=[_issue(title="New")],
        llmCompleted=True,
    )
    skipped = FindingReport(
        confidence=55,
        summary=Summary(),
        issues=[],
        llmSkipped=True,
        llmCompleted=False,
    )
    (out / "gate_review_report_review_2026-08-01_1200.json").write_text(
        old.model_dump_json(), encoding="utf-8"
    )
    (out / "gate_review_report_review_2026-08-05_1200.json").write_text(
        new.model_dump_json(), encoding="utf-8"
    )
    (out / "gate_review_report_review_2026-08-05_1300.json").write_text(
        skipped.model_dump_json(), encoding="utf-8"
    )
    # Ensure "new" is newest among completed (touch after skipped write).
    path_new = out / "gate_review_report_review_2026-08-05_1200.json"
    path_new.write_text(new.model_dump_json(), encoding="utf-8")
    bundled = bootstrap_from_out_dir(out)
    assert bundled is not None
    assert bundled[0].issues[0].title == "New"
