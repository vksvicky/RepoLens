"""Deep pass planner, file budgeting, merge/dedupe, and prompt builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.deep import (
    DeepPass,
    budget_files,
    build_deep_prompt,
    plan_deep_passes,
)
from repolens.inventory import FileEntry
from repolens.rules.registry import Rule
from repolens.schema import FindingReport, Issue, Summary


def _entry(relative: str, size: int, *, band: int = 3) -> FileEntry:
    return FileEntry(
        path=Path("/tmp") / relative,
        relative=relative,
        size=size,
        priority_band=band,
    )


def _rule(
    rule_id: str,
    band: str,
    *,
    body: str = "rule body",
    enabled: bool = True,
    coverage_ids: list[str] | None = None,
) -> Rule:
    return Rule(
        id=rule_id,
        band=band,
        enabled=enabled,
        title=rule_id.title(),
        body=body,
        coverage_ids=coverage_ids,
    )


def _issue(
    *,
    file: str = "a.py",
    title: str = "Finding",
    severity: str = "LOW",
    priority: str = "P3",
) -> Issue:
    return Issue.model_validate(
        {
            "severity": severity,
            "priority": priority,
            "category": "Test",
            "file": file,
            "line": 1,
            "title": title,
            "explanation": "x",
            "impact": "impact text" if severity in {"CRITICAL", "HIGH"} else "",
            "recommendedFix": "fix it",
            "codeExample": "code()" if severity in {"CRITICAL", "HIGH"} else "",
            "fixTiming": "before launch",
        }
    )


def _report(
    *,
    confidence: int,
    issues: list[Issue] | None = None,
    gaps: list[str] | None = None,
) -> FindingReport:
    issues = issues or []
    report = FindingReport(
        confidence=confidence,
        summary=Summary(),
        issues=issues,
        durabilityGaps=gaps or [],
    )
    report.summary = report.recount_summary()
    return report


def test_budget_files_never_exceeds_char_budget() -> None:
    entries = [
        _entry("small.py", 100),
        _entry("medium.py", 400),
        _entry("large.py", 300),
        _entry("overflow.py", 50),
    ]
    selected = budget_files(entries, max_chars=500)
    total = sum(e.size for e in selected)
    assert total <= 500
    assert [e.relative for e in selected] == ["small.py", "medium.py"]


def test_budget_files_skips_file_larger_than_budget_alone() -> None:
    entries = [
        _entry("huge.py", 1000),
        _entry("ok.py", 100),
    ]
    selected = budget_files(entries, max_chars=200)
    assert [e.relative for e in selected] == ["ok.py"]
    assert sum(e.size for e in selected) <= 200


def test_plan_deep_passes_review_orders_p1_p2_p3() -> None:
    rules = [
        _rule("architecture", "p3", coverage_ids=["arch.a"]),
        _rule("security", "p1", coverage_ids=["sec.a"]),
        _rule("reliability", "p2", coverage_ids=["rel.a"]),
    ]
    entries = [_entry("src/a.py", 50), _entry("src/b.py", 50)]
    passes = plan_deep_passes(
        "review",
        full_audit=False,
        entries=entries,
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=10_000,
        rules=rules,
    )
    assert [p.name for p in passes] == ["p1", "p2", "p3"]
    assert passes[0].rule_ids == ["security"]
    assert passes[1].rule_ids == ["reliability"]
    assert passes[2].rule_ids == ["architecture"]


def test_plan_deep_passes_max_passes_caps_bands() -> None:
    rules = [
        _rule("security", "p1"),
        _rule("reliability", "p2"),
        _rule("architecture", "p3"),
    ]
    passes = plan_deep_passes(
        "review",
        full_audit=False,
        entries=[_entry("a.py", 10)],
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=1000,
        rules=rules,
        max_passes=1,
    )
    assert [p.name for p in passes] == ["p1"]


def test_plan_deep_passes_sentinel_is_p1_only() -> None:
    rules = [
        _rule("security", "p1"),
        _rule("reliability", "p2"),
        _rule("architecture", "p3"),
    ]
    passes = plan_deep_passes(
        "sentinel",
        full_audit=False,
        entries=[_entry("a.py", 10)],
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=1000,
        rules=rules,
    )
    assert len(passes) == 1
    assert passes[0].name == "p1"
    assert passes[0].rule_ids == ["security"]


def test_plan_deep_passes_architecture_is_p3_only() -> None:
    rules = [
        _rule("security", "p1"),
        _rule("architecture", "p3"),
    ]
    passes = plan_deep_passes(
        "architecture",
        full_audit=True,
        entries=[_entry("a.py", 10)],
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=1000,
        rules=rules,
    )
    assert len(passes) == 1
    assert passes[0].name == "p3"
    assert passes[0].rule_ids == ["architecture"]


def test_plan_deep_passes_prefers_hot_and_adaptive_paths() -> None:
    rules = [_rule("security", "p1")]
    entries = [
        _entry("cold.py", 40),
        _entry("hot.py", 40),
        _entry("adaptive.py", 40),
        _entry("rest.py", 40),
    ]
    passes = plan_deep_passes(
        "sentinel",
        full_audit=False,
        entries=entries,
        hot_paths=["hot.py"],
        adaptive_paths=["adaptive.py"],
        chars_per_pass=80,
        rules=rules,
    )
    assert len(passes) == 1
    relatives = [e.relative for e in passes[0].files]
    assert relatives == ["hot.py", "adaptive.py"]
    assert sum(e.size for e in passes[0].files) <= 80


def test_plan_deep_passes_uses_coverage_ids_for_enabled_rules() -> None:
    rules = [
        _rule("security", "p1"),
        _rule("reliability", "p2"),
        _rule("architecture", "p3"),
    ]
    passes = plan_deep_passes(
        "review",
        full_audit=False,
        entries=[_entry("a.py", 10)],
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=1000,
        rules=rules,
    )
    assert passes[0].coverage_ids  # security matrix ids
    assert all(cid.startswith("sec.") for cid in passes[0].coverage_ids)
    assert all(cid.startswith("rel.") for cid in passes[1].coverage_ids)
    assert all(cid.startswith("arch.") for cid in passes[2].coverage_ids)


def test_build_deep_prompt_includes_rule_bodies_and_coverage_contract() -> None:
    rules = [
        _rule("security", "p1", body="## Security checklist\n- auth"),
        _rule("reliability", "p2", body="should not appear"),
    ]
    deep_pass = DeepPass(
        name="p1",
        rule_ids=["security"],
        coverage_ids=["sec.auth", "sec.secrets"],
        files=[_entry("a.py", 10)],
    )
    prompt = build_deep_prompt(deep_pass, rules, deep_pass.coverage_ids)
    assert "## Security checklist" in prompt
    assert "should not appear" not in prompt
    assert "sec.auth" in prompt
    assert "sec.secrets" in prompt
    assert "coverage:" in prompt
    assert "N/A" in prompt
    assert "durabilityGaps" in prompt


def test_plan_deep_passes_skips_disabled_and_unknown_mode() -> None:
    rules = [
        _rule("security", "p1", enabled=True),
        _rule("reliability", "p2", enabled=False),
    ]
    passes = plan_deep_passes(
        "review",
        full_audit=False,
        entries=[_entry("a.py", 10)],
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=1000,
        rules=[r for r in rules if r.enabled],
    )
    assert [p.name for p in passes] == ["p1"]
    with pytest.raises(ValueError):
        plan_deep_passes(
            "unknown",
            full_audit=False,
            entries=[],
            hot_paths=[],
            adaptive_paths=[],
            chars_per_pass=100,
            rules=rules,
        )


def test_deep_helpers_cover_degraded_passes_and_metrics(monkeypatch) -> None:
    """Extracted deep-pass helpers keep degraded, duplicate, and metric paths."""
    from types import SimpleNamespace

    from repolens.config import RepoLensConfig
    from repolens.coverage import CoverageResult
    from repolens.heuristics import HeuristicResult
    from repolens.pipeline.deep_exec import (
        _announce_deep_runtime,
        _fold_scanners,
        _load_deep_heuristics,
        _ollama_wait_bits,
        _ordered_unique,
        _pass_report,
        _phase_coverage_metrics,
    )
    from repolens.progress import LlmGenerateProgress, ReviewProgress

    cfg = RepoLensConfig()
    verbose = ReviewProgress(verbose=True)
    heur = _load_deep_heuristics(
        root=Path("."),
        files=[],
        cfg=cfg,
        prog=verbose,
        heur_result=HeuristicResult(hot_paths=["a.py"]),
        pack_ids=[],
    )
    assert heur.hot_paths == ["a.py"]

    _announce_deep_runtime(
        ReviewProgress(quiet=True),
        [SimpleNamespace(files=["a.py"])],
        cfg,
    )
    _announce_deep_runtime(ReviewProgress(), [SimpleNamespace(files=["a.py"])], cfg)

    monkeypatch.setattr(
        "repolens.provider_status.ollama_running_summary",
        lambda base: "ollama up" if base else None,
    )
    progress = LlmGenerateProgress()
    assert "ollama up" in " | ".join(_ollama_wait_bits(progress, "http://127.0.0.1:11434"))
    assert _ollama_wait_bits(progress, None)

    empty = _pass_report(SimpleNamespace(layer="degraded", report=None), "p1", verbose)
    assert empty.confidence == 0
    assert "llm.schema_invalid:p1" in empty.durabilityGaps
    kept = FindingReport(confidence=4, summary=Summary(), issues=[])
    assert _pass_report(SimpleNamespace(layer="ok", report=kept), "p2", verbose) is kept

    assert _ordered_unique(["a", "a", "b"]) == ["a", "b"]

    scanner_issue = Issue(
        severity="LOW",
        priority="P3",
        category="trivy",
        file="go.mod",
        line=1,
        title="noise",
        explanation="x",
        impact="",
        recommendedFix="upgrade",
        codeExample="",
    )
    folded = _fold_scanners(
        FindingReport(confidence=10, summary=Summary(), issues=[]),
        [scanner_issue],
        cfg,
        verbose,
    )
    assert any(i.category == "trivy" for i in folded.issues)

    report = FindingReport(confidence=10, summary=Summary(), issues=[])
    report.securityAuditConfidence = 20
    report.reliabilityAuditConfidence = 30
    report.architectureAuditConfidence = 40
    coverage = CoverageResult(
        covered=["sec.auth"],
        na={"sec.na": "out of scope"},
        missed=["sec.miss"],
    )
    _phase_coverage_metrics(verbose, report, coverage, ["sec.auth"])
    _phase_coverage_metrics(verbose, report, coverage, [])
