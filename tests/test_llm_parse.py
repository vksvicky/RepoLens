"""LLM JSON parse / repair helpers (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from repolens.config import ModelConfig
from repolens.llm import parse_report_json, repair_prompt
from repolens.llm_structured import analyze_structured


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


def test_coerce_null_code_example_keeps_high_severity() -> None:
    content = """{
      "confidence": 90,
      "summary": {"critical": 0, "high": 1, "medium": 0, "low": 0},
      "issues": [{
        "severity": "HIGH",
        "priority": "P1",
        "category": "arch.kiss",
        "file": "src/repolens/deep_budget.py",
        "line": 11,
        "title": "Near-clone block",
        "explanation": "Duplicated hints.",
        "impact": "Harder to maintain.",
        "recommendedFix": "Extract shared module.",
        "codeExample": null
      }],
      "durabilityGaps": []
    }"""
    report = parse_report_json(content)
    assert len(report.issues) == 1
    assert report.issues[0].severity.value == "HIGH"
    example = report.issues[0].codeExample.strip().lower()
    assert example
    assert "omitted" in example or "verify" in example


def test_coerce_empty_impact_and_code_example_strings() -> None:
    content = """{
      "confidence": 88,
      "summary": {"critical": 0, "high": 1, "medium": 0, "low": 0},
      "issues": [{
        "severity": "HIGH",
        "priority": "P2",
        "category": "rel.edge_cases",
        "file": "a.py",
        "line": 1,
        "title": "Complex control flow",
        "explanation": "Hard to test.",
        "impact": "",
        "recommendedFix": "Split helpers.",
        "codeExample": ""
      }],
      "durabilityGaps": []
    }"""
    report = parse_report_json(content)
    assert report.issues[0].severity.value == "HIGH"
    assert report.issues[0].impact.strip()
    assert report.issues[0].codeExample.strip()


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


def test_clean_review_notes_do_not_become_findings() -> None:
    content = """{
  "confidence": 80,
  "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "issues": [
    {
      "severity": "LOW",
      "priority": "P2",
      "category": "rel.edge_cases",
      "file": "scripts/repolens/assert_coverage.py",
      "line": 39,
      "title": "Reviewed edge cases; no issues found",
      "explanation": "The file checks coverage ids.",
      "recommendedFix": "None"
    },
    {
      "severity": "MEDIUM",
      "priority": "P2",
      "category": "Reliability",
      "file": "a.py",
      "line": 4,
      "title": "Bare except swallows errors",
      "explanation": "A failure becomes success.",
      "recommendedFix": "Catch OSError."
    }
  ],
  "durabilityGaps": []
}"""
    report = parse_report_json(content)
    assert [issue.title for issue in report.issues] == ["Bare except swallows errors"]
    assert any(
        gap.startswith("coverage:rel.edge_cases: N/A —") for gap in report.durabilityGaps
    )
    assert "apply the fix" not in " ".join(report.durabilityGaps)


def test_placeholder_fix_without_a_checklist_id_is_dropped() -> None:
    from repolens.llm.parse import _coverage_claim_gap, is_non_actionable_claim

    assert is_non_actionable_claim("SQL injection in the login query", "N/A")
    assert (
        _coverage_claim_gap(
            {
                "category": "Security",
                "title": "Reviewed auth; no issues found",
                "explanation": "Looked at the handler.",
            }
        )
        is None
    )
    note = _coverage_claim_gap(
        {"category": "sec.injection", "title": "", "explanation": ""}
    )
    assert note == "coverage:sec.injection: N/A — the model reported no defect"


def test_placeholder_fix_without_a_checklist_id_is_named() -> None:
    content = """{
      "confidence": 40,
      "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
      "issues": [{
        "severity": "HIGH",
        "priority": "P1",
        "category": "Security",
        "file": "src/login.py",
        "line": 12,
        "title": "SQL injection in the login query",
        "explanation": "The query concatenates the password.",
        "recommendedFix": "None",
        "impact": "Account takeover.",
        "codeExample": "query = \\"select \\" + password"
      }],
      "durabilityGaps": []
    }"""
    report = parse_report_json(content)
    assert report.issues == []
    assert report.durabilityGaps == [
        "llm.non_actionable_omitted: SQL injection in the login query"
    ]


def test_coerce_prepends_coverage_prefix_on_na_gaps() -> None:
    content = """{
      "confidence": 90,
      "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
      "issues": [],
      "durabilityGaps": [
        "arch.structure_size: N/A — CLI tool has no frontend",
        "coverage:rel.edge_cases: N/A — already prefixed"
      ]
    }"""
    report = parse_report_json(content)
    assert report.durabilityGaps[0].startswith("coverage:arch.structure_size:")
    assert report.durabilityGaps[1].startswith("coverage:rel.edge_cases:")


def test_repair_prompt_specializes_for_code_example_error() -> None:
    text = repair_prompt(
        "orig",
        "issues.0.codeExample: required for HIGH",
        hints=["Near-clone block"],
    )
    assert (
        "Issue 'Near-clone block' is HIGH but codeExample is null — provide "
        "codeExample or the tool will inject a placeholder."
    ) in text
    assert "JSON number" in text


def test_repair_prompt_without_code_example_error_has_no_hint_lines() -> None:
    text = repair_prompt("orig", "confidence not a number", hints=["X"])
    assert "codeExample is null" not in text


def test_repair_prompt_code_example_error_without_hints_stays_generic() -> None:
    text = repair_prompt("orig", "missing codeExample")
    assert "codeExample is null" not in text
    assert "codeExample" in text


def test_code_example_hints_from_raw_lists_high_issues_without_example() -> None:
    from repolens.llm.parse import code_example_hints

    raw = (
        '{"issues":[{"severity":"HIGH","title":"Near-clone block","codeExample":null},'
        '{"severity":"CRITICAL","title":"SQLi","codeExample":"x"},'
        '{"severity":"LOW","title":"Nit"},'
        '{"severity":"critical","title":"Missing key"}]}'
    )
    assert code_example_hints(raw) == ["Near-clone block", "Missing key"]
    assert code_example_hints("not json") == []


# --- Schema immunity suite (Task 7) -----------------------------------------

_GOOD_ISSUE = (
    '{"severity":"MEDIUM","priority":"P2","category":"rel.edge_cases",'
    '"file":"a.py","line":3,"title":"Bare except","explanation":"Swallows.",'
    '"recommendedFix":"Catch specific errors."}'
)
_VALID_BODY = (
    '{"confidence":80,"summary":{"critical":0,"high":0,"medium":1,"low":0},'
    f'"issues":[{_GOOD_ISSUE}],"durabilityGaps":[]}}'
)
_HIGH_NULL_FIELDS = (
    '{"confidence":90,"summary":{},"issues":[{"severity":"HIGH","priority":"P1",'
    '"category":"arch.kiss","file":"a.py","line":1,"title":"Clone","explanation":"Dup.",'
    '"impact":null,"recommendedFix":"Extract.","codeExample":null}],"durabilityGaps":[]}'
)

_RECOVERABLE_PAYLOADS = {
    "plain": _VALID_BODY,
    "fenced_json": f"```json\n{_VALID_BODY}\n```",
    "fenced_bare": f"```\n{_VALID_BODY}\n```",
    "fenced_uppercase_surrounding_whitespace": f"\n\n  ```json\n{_VALID_BODY}\n```  \n",
    "prose_prefix_and_suffix": f"Here is the report:\n{_VALID_BODY}\nHope that helps!",
    "string_confidence_percent": _VALID_BODY.replace('"confidence":80', '"confidence":"80%"'),
    "float_confidence": _VALID_BODY.replace('"confidence":80', '"confidence":79.6'),
    "garbage_confidence": _VALID_BODY.replace('"confidence":80', '"confidence":"high"'),
    "string_summary": _VALID_BODY.replace(
        '"summary":{"critical":0,"high":0,"medium":1,"low":0}', '"summary":"one medium"'
    ),
    "summary_with_string_counts": _VALID_BODY.replace('"medium":1', '"medium":"1"'),
    "findings_alias": _VALID_BODY.replace('"issues"', '"findings"'),
    "missing_issues_key": '{"confidence":70,"summary":{}}',
    "issues_null": '{"confidence":70,"summary":{},"issues":null,"durabilityGaps":null}',
    "issues_with_junk_entries": (
        '{"confidence":70,"summary":{},"issues":[null,42,"",[],'
        f"{_GOOD_ISSUE}]," '"durabilityGaps":[]}'
    ),
    "high_with_null_impact_and_code_example": _HIGH_NULL_FIELDS,
    "string_gap_instead_of_list": _VALID_BODY.replace(
        '"durabilityGaps":[]', '"durabilityGaps":"one gap"'
    ),
    "line_as_text": _VALID_BODY.replace('"line":3', '"line":"L42"'),
}


@pytest.mark.parametrize(
    "payload", list(_RECOVERABLE_PAYLOADS.values()), ids=list(_RECOVERABLE_PAYLOADS)
)
def test_immunity_recoverable_payloads_parse(payload: str) -> None:
    """Every known local-LLM drift shape coerces without a repair round-trip."""
    report = parse_report_json(payload)
    assert 0 <= report.confidence <= 100
    assert report.summary == report.recount_summary()


def test_immunity_null_fields_on_high_never_drop_the_finding() -> None:
    report = parse_report_json(_HIGH_NULL_FIELDS)
    assert [i.severity.value for i in report.issues] == ["HIGH"]
    assert report.summary.high == 1
    assert report.issues[0].impact.strip()
    assert report.issues[0].codeExample.strip()


def test_immunity_junk_issue_entries_are_dropped_not_fatal() -> None:
    report = parse_report_json(_RECOVERABLE_PAYLOADS["issues_with_junk_entries"])
    assert len(report.issues) == 1
    assert report.issues[0].title == "Bare except"


def test_immunity_line_text_is_coerced_to_integer() -> None:
    report = parse_report_json(_RECOVERABLE_PAYLOADS["line_as_text"])
    assert report.issues[0].line == 42


_UNRECOVERABLE_PAYLOADS = {
    "trailing_comma_object": _VALID_BODY.replace('"durabilityGaps":[]', '"durabilityGaps":[],'),
    "trailing_comma_array": _VALID_BODY.replace('"durabilityGaps":[]', '"durabilityGaps":["a",]'),
    "truncated_json": _VALID_BODY[:-25],
    "prose_only": "I could not review this repository.",
    "empty": "",
    "whitespace_only": "   \n  ",
    "fence_without_body": "```json\n```",
    "top_level_array": f"[{_GOOD_ISSUE}]",
    "top_level_string": '"just a string"',
}


@pytest.mark.parametrize(
    "payload", list(_UNRECOVERABLE_PAYLOADS.values()), ids=list(_UNRECOVERABLE_PAYLOADS)
)
def test_immunity_unrecoverable_payloads_raise_repairable_errors(payload: str) -> None:
    """Hard failures raise only error types the micro-repair spine catches."""
    with pytest.raises((json.JSONDecodeError, TypeError, ValueError)):
        parse_report_json(payload)


@pytest.fixture
def scripted_llm(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"responses": [], "prompts": []}

    def _fake(prompt: str, model_cfg: Any, *, client: Any = None, on_delta: Any = None) -> str:
        state["prompts"].append(prompt)
        return state["responses"].pop(0)

    monkeypatch.setattr("repolens.llm_structured.analyze_raw", _fake)
    return state


def _cfg() -> ModelConfig:
    # lock=False: keep the suite off the ~/.repolens model-lock filesystem boundary.
    return ModelConfig(provider="openai_compatible", api_key="dummy", lock=False)


@pytest.mark.parametrize(
    "payload", list(_RECOVERABLE_PAYLOADS.values()), ids=list(_RECOVERABLE_PAYLOADS)
)
def test_immunity_recoverable_payloads_never_spend_a_repair_call(
    payload: str, scripted_llm: dict[str, Any]
) -> None:
    scripted_llm["responses"] = [payload]
    result = analyze_structured("prompt", _cfg(), pass_id="p3")
    assert result.layer in {"ok", "coerced"}
    assert result.repair_attempts == 0
    assert len(scripted_llm["prompts"]) == 1


@pytest.mark.parametrize(
    "bad",
    [
        _UNRECOVERABLE_PAYLOADS["trailing_comma_object"],
        _UNRECOVERABLE_PAYLOADS["truncated_json"],
        _UNRECOVERABLE_PAYLOADS["prose_only"],
        _UNRECOVERABLE_PAYLOADS["top_level_array"],
    ],
    ids=["trailing_comma", "truncated", "prose_only", "top_level_array"],
)
def test_immunity_single_repair_path_recovers(
    bad: str, scripted_llm: dict[str, Any]
) -> None:
    scripted_llm["responses"] = [bad, _VALID_BODY]
    result = analyze_structured("prompt", _cfg(), pass_id="p3")
    assert result.layer == "micro_repair"
    assert result.repair_attempts == 1
    assert result.report is not None
    assert len(scripted_llm["prompts"]) == 2
    assert "previous JSON was invalid" in scripted_llm["prompts"][1]


def test_immunity_repair_is_capped_at_one_attempt(
    scripted_llm: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scripted_llm["responses"] = ["not json", "still not json", _VALID_BODY]
    result = analyze_structured("prompt", _cfg(), pass_id="p3")
    assert result.layer == "degraded"
    assert result.repair_attempts == 1
    assert len(scripted_llm["prompts"]) == 2
    assert len(scripted_llm["responses"]) == 1  # third response never requested
