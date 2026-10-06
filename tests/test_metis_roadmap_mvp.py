"""Plan forecast and diff-audit thin MVPs."""

from __future__ import annotations

from pathlib import Path

from repolens.config import AdaptiveConfig, DeepConfig, ModelConfig, RepoLensConfig
from repolens.diff_audit import diff_audit_reports
from repolens.feedback_store import record_feedback
from repolens.inventory import FileEntry
from repolens.learned_prefs import derive_learned_prefs, load_learned_prefs, save_learned_prefs
from repolens.na_truth import reject_false_na_claims
from repolens.plan_forecast import forecast_deep_plan
from repolens.schema import FindingReport, Issue, Severity, Summary
from repolens.verify_findings import apply_unverified_gate_penalty


def test_forecast_deep_plan_no_llm(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock"),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True, role_packs=False),
    )
    plan = forecast_deep_plan(tmp_path, cfg, mode="review")
    assert plan.inventory_kept >= 1
    assert plan.passes
    assert plan.total_estimated_chars >= 0
    assert "Slow Brain estimate" in plan.estimate_line


def test_forecast_role_packs_changes_modes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    for name in ("auth_login.py", "retry_backoff.py", "models_user.py"):
        (tmp_path / "src" / name).write_text("x = 1\n" * 20, encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock"),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True, role_packs=True, chars_per_pass=50_000),
    )
    plan = forecast_deep_plan(tmp_path, cfg, mode="review", full_audit=True)
    assert any(p.pack_mode == "outline" for p in plan.passes)


def test_diff_audit_detects_resolved_and_new() -> None:
    def _issue(title: str, file: str = "a.py") -> Issue:
        return Issue(
            severity=Severity.MEDIUM,
            priority="P2",
            category="rel.x",
            file=file,
            line=1,
            title=title,
            explanation="e",
            impact="",
            recommendedFix="fix",
            codeExample="",
        )

    left = FindingReport(
        confidence=70,
        summary=Summary(medium=2),
        issues=[_issue("Old"), _issue("Stay")],
    )
    right = FindingReport(
        confidence=80,
        summary=Summary(medium=2),
        issues=[_issue("Stay"), _issue("New")],
    )
    result = diff_audit_reports(left, right)
    assert "a.py:1:Old" in result.resolved
    assert "a.py:1:New" in result.new
    assert result.unchanged == 1
    assert result.confidence_delta == 10


def test_unverified_gate_penalty_lowers_confidence() -> None:
    issue = Issue(
        severity=Severity.CRITICAL,
        priority="P1",
        category="sec.x",
        file="a.py",
        line=1,
        title="Bad",
        explanation="e",
        impact="takeover",
        recommendedFix="fix",
        codeExample="x",
        verificationStatus="suspect",
    )
    report = FindingReport(
        confidence=90,
        summary=Summary(critical=1),
        issues=[issue],
        securityAuditConfidence=90,
    )
    out = apply_unverified_gate_penalty(report)
    assert out.confidence < 90
    assert out.securityAuditConfidence is not None and out.securityAuditConfidence < 90
    assert any("verify_suspect_penalty" in g for g in out.durabilityGaps)


def test_na_truth_rejects_absence_when_path_hints_match(tmp_path: Path) -> None:
    entries = [
        FileEntry(
            path=tmp_path / "src" / "auth" / "login.py",
            relative="src/auth/login.py",
            size=10,
            priority_band=1,
        )
    ]
    gaps = ["coverage:sec.auth: N/A — no authentication code present"]
    out = reject_false_na_claims(gaps, entries)
    assert any(g.startswith("hallucination_residual:sec.auth") for g in out)


def test_learned_prefs_from_repeated_feedback(tmp_path: Path) -> None:
    for i in range(2):
        record_feedback(
            tmp_path,
            stable_id=f"id-{i}",
            reason="false_positive",
            file=f"scripts/dev_tool_{i}.py",
            title="noise",
        )
    prefs = derive_learned_prefs(tmp_path)
    save_learned_prefs(tmp_path, prefs)
    loaded = load_learned_prefs(tmp_path)
    assert loaded.skip_globs
    assert any("scripts/" in g for g in loaded.skip_globs)


def test_learned_prefs_config_default_is_off() -> None:
    assert DeepConfig().learned_prefs is False
