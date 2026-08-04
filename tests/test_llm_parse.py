"""LLM JSON parse / repair helpers (no network)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from repolens.llm import parse_report_json, repair_prompt


def test_parse_fenced_json() -> None:
    content = """```json
{
  "schemaVersion": "1.0",
  "confidence": 77,
  "summary": {"critical": 0, "high": 0, "medium": 1, "low": 0},
  "issues": [{
    "severity": "MEDIUM",
    "priority": "P2",
    "category": "Reliability",
    "file": "a.py",
    "line": 1,
    "title": "Bare except",
    "explanation": "Swallows errors.",
    "recommendedFix": "Catch specific exceptions.",
    "codeExample": "",
    "fixTiming": "before launch"
  }],
  "durabilityGaps": []
}
```"""
    report = parse_report_json(content)
    assert report.confidence == 77
    assert report.summary.medium == 1


def test_parse_rejects_high_without_example() -> None:
    content = """{
  "confidence": 50,
  "summary": {"critical": 0, "high": 1, "medium": 0, "low": 0},
  "issues": [{
    "severity": "HIGH",
    "priority": "P1",
    "category": "Secrets",
    "file": "a.py",
    "line": 1,
    "title": "Key",
    "explanation": "Hardcoded.",
    "impact": "Leak",
    "recommendedFix": "Env var",
    "codeExample": ""
  }]
}"""
    with pytest.raises(ValidationError):
        parse_report_json(content)


def test_repair_prompt_mentions_schema() -> None:
    text = repair_prompt("original", "missing codeExample")
    assert "original" in text
    assert "codeExample" in text
