"""Shared fixtures for deep-pipeline tests."""

from __future__ import annotations

from collections.abc import Callable

from repolens.config import AdaptiveConfig, DeepConfig, ModelConfig, RepoLensConfig
from repolens.llm_structured import StructuredLlmResult
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


def ollama_deep_config() -> RepoLensConfig:
    """Mock Ollama settings with deep mode on."""
    return RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )


def _band_priority(pass_id: str) -> str:
    if pass_id == "p1":
        return "P1"
    if pass_id == "p2":
        return "P2"
    return "P3"


def recording_band_analyze(calls: list[str]) -> Callable[..., StructuredLlmResult]:
    """Record each pass id and return one finding for that band."""

    def analyze(
        prompt, model_cfg, *, pass_id, progress=None, raw_dir=None, on_delta=None, **_
    ):
        calls.append(pass_id)
        return _pass_report(
            title=f"{pass_id} finding",
            file="a.py",
            priority=_band_priority(pass_id),
            coverage_na=[],
        )

    return analyze
