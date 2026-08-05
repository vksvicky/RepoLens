"""Coerce and parse FindingReport JSON from LLM output."""

from __future__ import annotations

import json
import re
from typing import Any

from repolens.schema import FindingReport

def _first_str(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key not in data:
            continue
        val = data[key]
        if val is None:
            continue
        text = str(val).strip()
        if text:
            return text
    return default


def _coerce_severity(raw: Any) -> str:
    text = str(raw or "").strip().upper().replace(" ", "_")
    aliases = {
        "CRIT": "CRITICAL",
        "CRITICAL": "CRITICAL",
        "P1": "HIGH",
        "HIGH": "HIGH",
        "SEVERE": "HIGH",
        "ERROR": "HIGH",
        "P2": "MEDIUM",
        "MEDIUM": "MEDIUM",
        "MODERATE": "MEDIUM",
        "WARN": "MEDIUM",
        "WARNING": "MEDIUM",
        "P3": "LOW",
        "LOW": "LOW",
        "INFO": "LOW",
        "INFORMATIONAL": "LOW",
        "MINOR": "LOW",
    }
    if text in aliases:
        return aliases[text]
    for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if name in text:
            return name
    return "MEDIUM"


def _priority_for_severity(severity: str) -> str:
    if severity in {"CRITICAL", "HIGH"}:
        return "P1"
    if severity == "MEDIUM":
        return "P2"
    return "P3"


def _coerce_priority(raw: Any, *, severity: str) -> str:
    text = str(raw or "").strip().upper()
    if text in {"P1", "P2", "P3"}:
        return text
    if text in {"1", "HIGH", "CRITICAL"}:
        return "P1"
    if text in {"2", "MEDIUM"}:
        return "P2"
    if text in {"3", "LOW"}:
        return "P3"
    return _priority_for_severity(severity)


def _coerce_line(raw: Any) -> int:
    if isinstance(raw, bool):
        return 1
    if isinstance(raw, int):
        return raw if raw >= 1 else 1
    if isinstance(raw, float):
        return int(raw) if raw >= 1 else 1
    if isinstance(raw, str):
        match = re.search(r"\d+", raw)
        if match:
            value = int(match.group(0))
            return value if value >= 1 else 1
    return 1


def _coerce_fix_timing(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    allowed = {
        "immediately",
        "before launch",
        "after launch",
        "if time permits",
    }
    if text in allowed:
        return text
    if "immediate" in text:
        return "immediately"
    if "after" in text:
        return "after launch"
    if "permit" in text or "later" in text:
        return "if time permits"
    return "before launch"


def _coerce_issue(raw: Any) -> dict[str, Any] | None:
    """Normalize one issue object; drop entries that cannot become useful findings."""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        raw = {"title": text[:120], "explanation": text}
    if not isinstance(raw, dict):
        return None

    # Flatten common wrappers
    for nest_key in ("issue", "finding", "item"):
        nested = raw.get(nest_key)
        if isinstance(nested, dict):
            merged = dict(nested)
            merged.update({k: v for k, v in raw.items() if k != nest_key})
            raw = merged
            break

    sev_source = raw.get("severity") or raw.get("Severity") or raw.get("level")
    if sev_source is None or str(sev_source).strip() == "":
        sev_source = raw.get("priority")  # e.g. only "P1" provided
    severity = _coerce_severity(sev_source)
    priority = _coerce_priority(
        raw.get("priority") or raw.get("Priority") or raw.get("pri"),
        severity=severity,
    )

    title = _first_str(raw, "title", "name", "summary", "heading", default="")
    explanation = _first_str(
        raw,
        "explanation",
        "description",
        "details",
        "detail",
        "rationale",
        "message",
        default="",
    )
    if not title and explanation:
        title = explanation[:120]
    if not explanation and title:
        explanation = title
    if not title and not explanation:
        return None

    recommended = _first_str(
        raw,
        "recommendedFix",
        "recommended_fix",
        "recommendation",
        "fix",
        "remediation",
        "solution",
        default="Review and remediate manually.",
    )
    impact = _first_str(raw, "impact", "risk", "consequence", default="")
    code_example = _first_str(
        raw, "codeExample", "code_example", "example", "snippet", default=""
    )
    # Fill Critical/High gates only when the model omitted the keys entirely
    # (explicit empty strings still fail validation — keep that contract).
    if severity in {"CRITICAL", "HIGH"}:
        if not impact and not any(k in raw for k in ("impact", "risk", "consequence")):
            impact = "(Model omitted impact — verify manually.)"
        if not code_example and not any(
            k in raw for k in ("codeExample", "code_example", "example", "snippet")
        ):
            code_example = "// Model omitted codeExample — verify manually.\n"

    file_path = _first_str(
        raw,
        "file",
        "path",
        "filePath",
        "file_path",
        "filename",
        "location",
        default="(unspecified)",
    )
    category = _first_str(
        raw, "category", "type", "kind", "area", default="General"
    )

    return {
        "severity": severity,
        "priority": priority,
        "category": category,
        "file": file_path,
        "line": _coerce_line(raw.get("line") or raw.get("lineNumber") or raw.get("lineno")),
        "title": title,
        "explanation": explanation,
        "impact": impact,
        "recommendedFix": recommended,
        "codeExample": code_example,
        "fixTiming": _coerce_fix_timing(
            raw.get("fixTiming") or raw.get("fix_timing") or raw.get("when")
        ),
        "cwe": raw.get("cwe"),
        "owasp": raw.get("owasp"),
    }


def _coerce_report_payload(raw: Any) -> dict[str, Any]:
    """Normalize common local-LLM JSON mistakes before Pydantic validation."""
    if not isinstance(raw, dict):
        raise TypeError(f"FindingReport JSON must be an object, got {type(raw).__name__}")
    data = dict(raw)

    conf = data.get("confidence", 0)
    if isinstance(conf, str):
        conf = conf.strip().rstrip("%")
        try:
            conf = int(float(conf))
        except ValueError:
            conf = 0
    elif isinstance(conf, float):
        conf = int(conf)
    data["confidence"] = conf

    summary = data.get("summary")
    if not isinstance(summary, dict):
        # Models sometimes emit a string or list; recount_summary will fix counts.
        data["summary"] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
    else:
        fixed: dict[str, Any] = {}
        for key in ("critical", "high", "medium", "low"):
            val = summary.get(key, 0)
            if isinstance(val, str):
                try:
                    val = int(float(val.strip()))
                except ValueError:
                    val = 0
            elif isinstance(val, float):
                val = int(val)
            fixed[key] = val if isinstance(val, int) else 0
        data["summary"] = fixed

    issues_raw = data.get("issues")
    if not isinstance(issues_raw, list):
        # Some models nest findings under findings/results
        for alt in ("findings", "results", "problems"):
            if isinstance(data.get(alt), list):
                issues_raw = data[alt]
                break
        else:
            issues_raw = []
    coerced_issues: list[dict[str, Any]] = []
    for item in issues_raw:
        issue = _coerce_issue(item)
        if issue is not None:
            coerced_issues.append(issue)
    data["issues"] = coerced_issues

    gaps = data.get("durabilityGaps")
    if gaps is None:
        gaps = data.get("durability_gaps") or data.get("gaps") or []
    if isinstance(gaps, str):
        gaps = [gaps] if gaps.strip() else []
    if not isinstance(gaps, list):
        gaps = []
    data["durabilityGaps"] = [str(g) for g in gaps if str(g).strip()]

    return data


def parse_report_json(content: str) -> FindingReport:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        raw = json.loads(match.group(0))
    report = FindingReport.model_validate(_coerce_report_payload(raw))
    # Keep summary consistent with issues when model drifts
    counted = report.recount_summary()
    report.summary = counted
    return report


def repair_prompt(original: str, error: str) -> str:
    return (
        f"{original}\n\n---\nYour previous JSON was invalid: {error}\n"
        "Return corrected FindingReport JSON only with this exact shape:\n"
        '{"schemaVersion":"1.0","confidence":<integer 0-100>,'
        '"summary":{"critical":0,"high":0,"medium":0,"low":0},'
        '"issues":[...],"durabilityGaps":[]}\n'
        "confidence MUST be a JSON number (not a string). "
        "summary MUST be an object with integer fields. "
        "Each issue MUST use keys: severity (CRITICAL|HIGH|MEDIUM|LOW), "
        "priority (P1|P2|P3), category, file, line (integer), title, "
        "explanation, recommendedFix; Critical/High also need impact and codeExample."
    )
