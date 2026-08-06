"""Unit tests for LLM consistency decision parsing (no network)."""

from __future__ import annotations

from unittest.mock import patch

from repolens.config import DeepConfig, ModelConfig
from repolens.consistency import apply_llm_consistency
from repolens.schema import Issue, Severity


def _critical_llm() -> Issue:
    return Issue(
        severity=Severity.CRITICAL,
        priority="P1",
        category="sec.injection",
        file="a.py",
        line=1,
        title="Bad",
        explanation="x",
        impact="Attacker may exploit this.",
        recommendedFix="fix",
        codeExample="return safe()",
        source="llm",
    )


def test_llm_consistency_demote_from_json() -> None:
    cfg = DeepConfig(critical_consistency="llm")
    model = ModelConfig(provider="openai", model="gpt-test")
    raw = '{"decisions":[{"index":0,"action":"demote","severity":"MEDIUM"}]}'
    with patch("repolens.llm.analyze_raw", return_value=raw):
        out = apply_llm_consistency([_critical_llm()], cfg, model)
    assert out[0].severity == Severity.MEDIUM
    assert "[unconfirmed: consistency]" in out[0].explanation


def test_llm_consistency_refuses_upgrade() -> None:
    cfg = DeepConfig(critical_consistency="llm")
    model = ModelConfig(provider="openai", model="gpt-test")
    raw = '{"decisions":[{"index":0,"action":"demote","severity":"CRITICAL"}]}'
    with patch("repolens.llm.analyze_raw", return_value=raw):
        out = apply_llm_consistency([_critical_llm()], cfg, model)
    # Falls back to one-band demote
    assert out[0].severity == Severity.HIGH
