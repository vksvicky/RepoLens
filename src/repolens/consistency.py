"""Critical/High self-consistency (Phase 6.7) — heuristic + optional LLM confirm."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from repolens.config import DeepConfig, ModelConfig
from repolens.schema import Issue, Severity
from repolens.triage import infer_issue_source

_DEMOTE = {
    Severity.CRITICAL: Severity.HIGH,
    Severity.HIGH: Severity.MEDIUM,
    Severity.MEDIUM: Severity.LOW,
}

_UNCONFIRMED = "[unconfirmed: location]"
_LLM_UNCONFIRMED = "[unconfirmed: consistency]"


class ConsistencyDecision(BaseModel):
    index: int = Field(ge=0)
    action: str  # agree | demote
    severity: str | None = None


class ConsistencyResponse(BaseModel):
    decisions: list[ConsistencyDecision] = Field(default_factory=list)


def _mode(deep: DeepConfig) -> str:
    raw = (deep.critical_consistency or "off").strip().lower()
    if raw in {"off", "heuristic", "llm"}:
        return raw
    return "off"


def _targets(issues: list[Issue], deep: DeepConfig) -> list[tuple[int, Issue]]:
    include_high = bool(deep.critical_consistency_include_high)
    out: list[tuple[int, Issue]] = []
    for i, issue in enumerate(issues):
        if infer_issue_source(issue) == "scanner":
            continue
        if issue.severity == Severity.CRITICAL:
            out.append((i, issue))
        elif include_high and issue.severity == Severity.HIGH:
            out.append((i, issue))
    return out


def _demote_one(issue: Issue, tag: str) -> Issue:
    new_sev = _DEMOTE.get(issue.severity)
    if new_sev is None:
        return issue
    explanation = issue.explanation
    if tag not in explanation:
        explanation = f"{tag} {explanation}"
    return issue.model_copy(update={"severity": new_sev, "explanation": explanation})


def apply_heuristic_consistency(
    issues: list[Issue], deep: DeepConfig
) -> list[Issue]:
    """Demote unverified Critical(/High) LLM/heuristic findings one band."""
    mode = _mode(deep)
    if mode == "off":
        return issues
    # heuristic runs for both heuristic and llm modes (llm adds a prior confirm pass)
    out = list(issues)
    for idx, issue in _targets(out, deep):
        if issue.locationVerified is False:
            out[idx] = _demote_one(issue, _UNCONFIRMED)
    return out


def _build_confirm_prompt(targets: list[tuple[int, Issue]]) -> str:
    rows: list[dict[str, Any]] = []
    for idx, issue in targets:
        rows.append(
            {
                "index": idx,
                "severity": issue.severity.value,
                "category": issue.category,
                "file": issue.file,
                "line": issue.line,
                "title": issue.title,
                "explanation": (issue.explanation or "")[:800],
            }
        )
    return (
        "You are confirming Critical/High security findings from a prior pass.\n"
        "For each finding, decide agree (keep severity) or demote (one band lower).\n"
        "Respond with JSON only:\n"
        '{"decisions":[{"index":0,"action":"agree|demote","severity":null}]}\n'
        "If demoting, set severity to the new level (HIGH|MEDIUM|LOW).\n"
        f"Findings:\n{json.dumps(rows, indent=2)}\n"
    )


def _parse_decisions(raw: str) -> ConsistencyResponse | None:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        return ConsistencyResponse.model_validate(data)
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def apply_llm_consistency(
    issues: list[Issue],
    deep: DeepConfig,
    model_cfg: ModelConfig,
) -> list[Issue]:
    """Optional second-pass confirm for Critical(/High) LLM findings.

    Non-fatal: on transport/parse failure, returns issues unchanged.
    """
    if _mode(deep) != "llm":
        return issues
    targets = _targets(issues, deep)
    # Only re-check rows that still look Critical/High and are llm-sourced
    targets = [(i, iss) for i, iss in targets if infer_issue_source(iss) == "llm"]
    if not targets:
        return issues

    from repolens.llm import LlmError, analyze_raw

    prompt = _build_confirm_prompt(targets)
    try:
        raw = analyze_raw(prompt, model_cfg)
    except LlmError:
        return issues
    parsed = _parse_decisions(raw)
    if parsed is None:
        return issues

    out = list(issues)
    by_index = {d.index: d for d in parsed.decisions}
    for idx, issue in targets:
        decision = by_index.get(idx)
        if decision is None:
            continue
        action = (decision.action or "").strip().lower()
        if action != "demote":
            continue
        if decision.severity:
            try:
                new_sev = Severity(decision.severity.strip().upper())
            except ValueError:
                out[idx] = _demote_one(issue, _LLM_UNCONFIRMED)
                continue
            order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
            if order.index(new_sev) >= order.index(issue.severity):
                # Refuse upgrades / same severity
                out[idx] = _demote_one(issue, _LLM_UNCONFIRMED)
            else:
                explanation = issue.explanation
                if _LLM_UNCONFIRMED not in explanation:
                    explanation = f"{_LLM_UNCONFIRMED} {explanation}"
                out[idx] = issue.model_copy(
                    update={"severity": new_sev, "explanation": explanation}
                )
        else:
            out[idx] = _demote_one(issue, _LLM_UNCONFIRMED)
    return out
