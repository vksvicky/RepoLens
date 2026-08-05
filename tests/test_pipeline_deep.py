"""Deep mode wired into run_review (mocked LLM per pass)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from repolens.config import AdaptiveConfig, DeepConfig, ModelConfig, RepoLensConfig
from repolens.llm_structured import StructuredLlmResult
from repolens.pipeline import run_review
from repolens.progress import ReviewProgress
from repolens.report import render_markdown
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(
    *,
    file: str,
    title: str,
    priority: str = "P1",
    severity: Severity = Severity.LOW,
) -> Issue:
    return Issue(
        severity=severity,
        priority=priority,  # type: ignore[arg-type]
        category="test",
        file=file,
        line=1,
        title=title,
        explanation=f"Addresses checklist theme for {title}",
        impact="",
        recommendedFix="fix it",
        codeExample="",
    )


def _pass_report(
    *,
    title: str,
    file: str,
    priority: str,
    coverage_na: list[str],
) -> StructuredLlmResult:
    gaps = [f"coverage:{cid}: N/A — not applicable in fixture" for cid in coverage_na]
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[_issue(file=file, title=title, priority=priority)],
        durabilityGaps=gaps,
    )
    report.summary = report.recount_summary()
    return StructuredLlmResult(
        report=report, raw_text="{}", layer="ok", error=None
    )


def test_deep_mode_merges_three_passes_heuristics_and_lists_coverage(
    tmp_path: Path,
) -> None:
    # Mega-file triggers heuristics (≥500 LOC).
    mega = tmp_path / "LocalizedString.swift"
    mega.write_text("\n".join(f"let x{i} = {i}" for i in range(520)) + "\n", encoding="utf-8")
    (tmp_path / "auth.py").write_text("def login(): pass\n", encoding="utf-8")

    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True, mega_file_lines=500),
    )

    call_pass_ids: list[str] = []

    def fake_analyze(prompt, model_cfg, *, pass_id, progress=None, raw_dir=None):
        call_pass_ids.append(pass_id)
        if pass_id == "p1":
            return _pass_report(
                title="P1 finding",
                file="auth.py",
                priority="P1",
                coverage_na=["sec.injection"],
            )
        if pass_id == "p2":
            return _pass_report(
                title="P2 finding",
                file="auth.py",
                priority="P2",
                coverage_na=["rel.edge_cases"],
            )
        if pass_id == "p3":
            return _pass_report(
                title="P3 finding",
                file="auth.py",
                priority="P3",
                coverage_na=["arch.structure"],
            )
        raise AssertionError(f"unexpected pass_id {pass_id!r}")

    with patch(
        "repolens.llm_structured.analyze_structured", side_effect=fake_analyze
    ) as mocked:
        result = run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )

    assert mocked.call_count == 3
    assert call_pass_ids == ["p1", "p2", "p3"]

    titles = {i.title for i in result.report.issues}
    assert "P1 finding" in titles
    assert "P2 finding" in titles
    assert "P3 finding" in titles
    # Heuristic mega-file finding merged in
    assert any("mega" in i.title.lower() or i.file.endswith(".swift") for i in result.report.issues)

    gaps = result.report.durabilityGaps
    assert any(g.startswith("coverage:sec.injection:") for g in gaps)
    # Missed coverage ids (neither issue nor N/A) appear as durability gaps
    assert any("coverage:" in g and "missed" in g.lower() for g in gaps)

    md = render_markdown(
        result.report, mode="review", commit_go="n/a", push_go="n/a"
    )
    assert "## Coverage" in md
    assert "sec.injection" in md or "N/A" in md


def test_deep_waiting_once_per_pass(tmp_path: Path) -> None:
    """Deep path resets progress waiting per pass (not one cumulative wrap)."""
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )
    fake = FindingReport(confidence=40, summary=Summary(), issues=[])
    fake_result = StructuredLlmResult(
        report=fake, raw_text="{}", layer="ok", error=None
    )
    waiting_labels: list[str] = []

    @contextmanager
    def fake_waiting(self, message: str, **_kwargs):
        waiting_labels.append(message)
        yield

    with (
        patch("repolens.llm_structured.analyze_structured", return_value=fake_result),
        patch.object(ReviewProgress, "waiting", fake_waiting),
    ):
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )

    deep_waits = [m for m in waiting_labels if m.startswith("Deep pass ")]
    assert len(deep_waits) == 3
    assert "Deep pass 1/3 (p1)" in deep_waits[0]
    assert "Deep pass 2/3 (p2)" in deep_waits[1]
    assert "Deep pass 3/3 (p3)" in deep_waits[2]
    assert "mock" in deep_waits[0]
    assert "ollama" in deep_waits[0]
    # No single outer LLM wait wrapping all passes.
    assert not any(m.startswith("LLM:") for m in waiting_labels)


def test_no_deep_keeps_outer_waiting(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )
    fake = FindingReport(confidence=50, summary=Summary(), issues=[])
    fake_result = StructuredLlmResult(
        report=fake, raw_text="{}", layer="ok", error=None
    )
    waiting_labels: list[str] = []

    @contextmanager
    def fake_waiting(self, message: str, **_kwargs):
        waiting_labels.append(message)
        yield

    with (
        patch("repolens.llm_structured.analyze_structured", return_value=fake_result),
        patch.object(ReviewProgress, "waiting", fake_waiting),
    ):
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=False,
        )

    assert len(waiting_labels) == 1
    assert waiting_labels[0].startswith("LLM:")
    assert "mock" in waiting_labels[0]


def test_no_deep_uses_single_shot_analyze(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),  # config on, CLI/flag overrides off
    )
    fake = FindingReport(
        confidence=50,
        summary=Summary(low=1),
        issues=[_issue(file="a.py", title="Single shot")],
    )
    fake_result = StructuredLlmResult(
        report=fake, raw_text="{}", layer="ok", error=None
    )

    with patch(
        "repolens.llm_structured.analyze_structured", return_value=fake_result
    ) as mocked:
        result = run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=False,
        )

    assert mocked.call_count == 1
    assert mocked.call_args.kwargs.get("pass_id") == "single"
    assert any(i.title == "Single shot" for i in result.report.issues)


def test_deep_default_on_for_llm_runs(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        # DeepConfig default enabled=True
    )
    fake = FindingReport(confidence=40, summary=Summary(), issues=[])
    fake_result = StructuredLlmResult(
        report=fake, raw_text="{}", layer="ok", error=None
    )

    with patch(
        "repolens.llm_structured.analyze_structured", return_value=fake_result
    ) as mocked:
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            # deep=None → config default (on)
        )

    assert mocked.call_count == 3
    pass_ids = [c.kwargs.get("pass_id") for c in mocked.call_args_list]
    assert pass_ids == ["p1", "p2", "p3"]


def test_deep_metrics_penalize_lazy_na_and_render_glossary(tmp_path: Path) -> None:
    """High LLM confidence + lazy N/A → gate/security audit < 95; Metrics section present."""
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )

    def fake_analyze(prompt, model_cfg, *, pass_id, progress=None, raw_dir=None):
        report = FindingReport(
            confidence=95,
            summary=Summary(),
            issues=[
                _issue(
                    file="a.py",
                    title=f"{pass_id} finding",
                    priority="P1" if pass_id == "p1" else "P2" if pass_id == "p2" else "P3",
                )
            ],
            durabilityGaps=[
                "coverage:sec.injection: N/A — not reviewed in this document",
                "coverage:sec.xss_csrf: N/A — not explicitly reviewed",
            ]
            if pass_id == "p1"
            else [],
        )
        report.summary = report.recount_summary()
        return StructuredLlmResult(
            report=report, raw_text="{}", layer="ok", error=None
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        result = run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )

    assert result.report.confidence < 95
    assert result.report.securityAuditConfidence is not None
    assert result.report.securityAuditConfidence < 95
    assert any("lazy N/A" in g or "missed" in g for g in result.report.durabilityGaps)
    md = render_markdown(
        result.report, mode="review", commit_go="n/a", push_go="n/a"
    )
    assert "## Metrics" in md
    assert "Security audit confidence" in md
    assert "% secure" in md


def test_degraded_pass_still_merges(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )

    def fake_analyze(prompt, model_cfg, *, pass_id, progress=None, raw_dir=None):
        if pass_id == "p1":
            return StructuredLlmResult(
                report=FindingReport(
                    confidence=0,
                    summary=Summary(),
                    issues=[],
                    durabilityGaps=["llm.schema_invalid:p1"],
                ),
                raw_text="not json",
                layer="degraded",
                error="parse failed",
            )
        return _pass_report(
            title=f"{pass_id} ok",
            file="a.py",
            priority="P2" if pass_id == "p2" else "P3",
            coverage_na=[],
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        result = run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )

    titles = {i.title for i in result.report.issues}
    assert "p2 ok" in titles
    assert "p3 ok" in titles
    assert any("llm.schema_invalid" in g for g in result.report.durabilityGaps)
