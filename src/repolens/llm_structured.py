"""Structured LLM spine (ask -> coerce -> micro-repair -> degrade)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from repolens.config import ModelConfig
from repolens.llm import (
    LlmError,
    _coerce_report_payload,
    analyze_raw,
    parse_report_json,
    repair_prompt,
)
from repolens.progress import ReviewProgress, null_progress
from repolens.schema import FindingReport, Summary


@dataclass
class StructuredLlmResult:
    report: FindingReport | None
    raw_text: str
    layer: Literal["ok", "coerced", "micro_repair", "degraded"]
    error: str | None


def analyze_structured(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    pass_id: str,
    progress: ReviewProgress | None = None,
    raw_dir: Path | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> StructuredLlmResult:
    prog = progress or null_progress()
    save_root = raw_dir if raw_dir is not None else Path(".repolens")

    try:
        raw_text = analyze_raw(prompt, model_cfg, on_delta=on_delta)
    except LlmError as exc:
        return _degrade_result("", str(exc), pass_id, prog, save_root)

    # Coerce / parse
    try:
        report = parse_report_json(raw_text)
        layer: Literal["ok", "coerced"] = (
            "coerced" if _looks_coerced(raw_text) else "ok"
        )
        return StructuredLlmResult(
            report=report,
            raw_text=raw_text,
            layer=layer,
            error=None,
        )
    except (LlmError, ValidationError, json.JSONDecodeError, TypeError, ValueError) as parse_exc:
        # Micro-repair
        prog.phase("LLM: first response invalid — retrying with repair prompt…")
        repair_msg = repair_prompt(raw_text, str(parse_exc))
        try:
            repaired_raw = analyze_raw(repair_msg, model_cfg, on_delta=on_delta)
            try:
                report = parse_report_json(repaired_raw)
                return StructuredLlmResult(
                    report=report,
                    raw_text=repaired_raw,
                    layer="micro_repair",
                    error=None,
                )
            except (
                LlmError,
                ValidationError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ) as repair_parse_exc:
                return _degrade_result(
                    repaired_raw, str(repair_parse_exc), pass_id, prog, save_root
                )
        except LlmError as repair_net_exc:
            return _degrade_result(raw_text, str(repair_net_exc), pass_id, prog, save_root)


def _looks_coerced(raw_text: str) -> bool:
    """Heuristic: freestyle markers that required coercion (not strict schema JSON)."""
    try:
        payload = json.loads(raw_text.strip().removeprefix("```json").removeprefix("```").strip())
    except json.JSONDecodeError:
        return True
    if not isinstance(payload, dict):
        return True
    conf = payload.get("confidence")
    if isinstance(conf, str):
        return True
    for issue in payload.get("issues") or []:
        if not isinstance(issue, dict):
            return True
        sev = issue.get("severity")
        if isinstance(sev, str) and sev.upper() not in {
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW",
        }:
            return True
    return False


def _degrade_result(
    raw_text: str,
    error_msg: str,
    pass_id: str,
    prog: ReviewProgress,
    save_root: Path,
) -> StructuredLlmResult:
    prog.phase(f"LLM: analysis degraded for pass '{pass_id}': {error_msg}")

    # Save raw output under project .repolens (or caller-provided dir)
    save_dir = save_root
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"last_llm_raw_{pass_id}.txt"
    try:
        if raw_text:
            save_path.write_text(raw_text, encoding="utf-8")
            prog.detail(f"Saved raw LLM output to {save_path}")
    except OSError:
        pass

    salvaged_report = None
    if raw_text:
        try:
            text = raw_text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                raw = json.loads(match.group(0))
                payload = _coerce_report_payload(raw)
                salvaged_report = FindingReport.model_validate(payload)
                salvaged_report.summary = salvaged_report.recount_summary()
        except Exception:
            pass

    if salvaged_report is None:
        salvaged_report = FindingReport(
            confidence=0,
            summary=Summary(),
            issues=[],
            durabilityGaps=[],
        )

    gap_msg = f"llm.schema_invalid (pass: {pass_id}): {error_msg}"
    if not salvaged_report.durabilityGaps:
        salvaged_report.durabilityGaps = []
    salvaged_report.durabilityGaps.append(gap_msg)

    return StructuredLlmResult(
        report=salvaged_report,
        raw_text=raw_text,
        layer="degraded",
        error=error_msg,
    )
