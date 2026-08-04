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
    assert "JSON number" in text


def test_parse_coerces_string_confidence_and_bad_summary() -> None:
    content = """{
  "confidence": "72%",
  "summary": "three medium issues",
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
}"""
    report = parse_report_json(content)
    assert report.confidence == 72
    assert report.summary.medium == 1


def test_parse_coerces_messy_local_llm_issues() -> None:
    """qwen-style issues: lowercase severity, aliases, missing priority/fields."""
    content = """{
  "confidence": 65,
  "summary": {"critical": 0, "high": 1, "medium": 1, "low": 0},
  "issues": [
    {
      "severity": "high",
      "path": "scripts/notarize.sh",
      "line": "42",
      "name": "Secrets via env in scripts",
      "description": "Notarization docs expect APPLE_ID password in env.",
      "recommendation": "Use Keychain / CI secrets; document .env in gitignore.",
      "type": "Secrets"
    },
    {
      "severity": "Medium",
      "file": "PatternSorcerer/Core/Utilities/LocalizedString.swift",
      "title": "Mega enum",
      "explanation": "637-line LocalizedString is hard to maintain.",
      "recommended_fix": "Split by feature domain."
    },
    {
      "severity": "P1",
      "category": "Architecture",
      "file": "ExtractToolView.swift",
      "line": 1,
      "title": "Duplication",
      "explanation": "Near-duplicate of ReplaceToolView.",
      "recommendedFix": "Extract shared component."
    }
  ],
  "durabilityGaps": []
}"""
    report = parse_report_json(content)
    assert len(report.issues) == 3
    assert report.issues[0].severity.value == "HIGH"
    assert report.issues[0].priority == "P1"
    assert report.issues[0].file == "scripts/notarize.sh"
    assert report.issues[0].line == 42
    assert report.issues[0].title == "Secrets via env in scripts"
    assert "Keychain" in report.issues[0].recommendedFix
    assert report.issues[0].impact  # placeholder allowed for coerced HIGH
    assert report.issues[0].codeExample
    assert report.issues[1].severity.value == "MEDIUM"
    assert report.issues[1].priority == "P2"
    assert "LocalizedString" in report.issues[1].file
    assert report.issues[2].severity.value == "HIGH"  # P1 → HIGH
    assert report.summary.high == 2
    assert report.summary.medium == 1
