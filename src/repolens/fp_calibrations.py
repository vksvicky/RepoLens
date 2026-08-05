"""Post-LLM false-positive calibrations (toggleable via ``[deep].fp_calibrations``)."""

from __future__ import annotations

import re

from repolens.config import DeepConfig
from repolens.schema import Issue, Severity

CALIBRATION_SUBPROCESS_LIST = "subprocess_list_not_injection"

# Packaged defaults — omit key in config to use these; set false to disable.
DEFAULT_FP_CALIBRATIONS: dict[str, bool] = {
    CALIBRATION_SUBPROCESS_LIST: True,
}

_CALIBRATED_PREFIX = f"[calibrated: {CALIBRATION_SUBPROCESS_LIST}]"

_INJECTION_HINT = re.compile(
    r"sec\.injection|command\s+injection|subprocess",
    re.IGNORECASE,
)
_SHELL_TRUE = re.compile(r"shell\s*=\s*True")
_SHELL_FALSE = re.compile(r"shell\s*=\s*False")
_SUBPROCESS_CALL = re.compile(
    r"subprocess\.(?:run|Popen|call|check_call|check_output)\s*\(",
    re.IGNORECASE,
)
# List / argv-style first arg (not a string literal shell command).
_LIST_OR_ARGV_FIRST = re.compile(
    r"subprocess\.(?:run|Popen|call|check_call|check_output)\s*\(\s*"
    r"(?:argv|args|cmd|command|\[[^\]]*\])",
    re.IGNORECASE,
)


def effective_fp_calibrations(deep: DeepConfig) -> dict[str, bool]:
    """Merge packaged defaults with ``deep.fp_calibrations`` overrides."""
    resolved = dict(DEFAULT_FP_CALIBRATIONS)
    for key, value in (deep.fp_calibrations or {}).items():
        if key in resolved:
            resolved[key] = bool(value)
        # Unknown ids ignored (forward-compatible).
    return resolved


def apply_fp_calibrations(issues: list[Issue], deep: DeepConfig) -> list[Issue]:
    """Return issues with enabled calibrations applied (demote, do not drop)."""
    enabled = effective_fp_calibrations(deep)
    out: list[Issue] = []
    for issue in issues:
        current = issue
        if enabled.get(CALIBRATION_SUBPROCESS_LIST):
            current = _calibrate_subprocess_list(current)
        out.append(current)
    return out


def _issue_text(issue: Issue) -> str:
    return "\n".join(
        [
            issue.category,
            issue.title,
            issue.explanation,
            issue.codeExample,
            issue.recommendedFix,
        ]
    )


def _looks_like_safe_list_subprocess(text: str) -> bool:
    if not _SUBPROCESS_CALL.search(text):
        return False
    if _SHELL_TRUE.search(text):
        return False
    if _LIST_OR_ARGV_FIRST.search(text):
        return True
    if _SHELL_FALSE.search(text):
        return True
    return False


def _calibrate_subprocess_list(issue: Issue) -> Issue:
    if issue.severity not in {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}:
        return issue
    text = _issue_text(issue)
    if not _INJECTION_HINT.search(text):
        return issue
    if not _looks_like_safe_list_subprocess(text):
        return issue
    explanation = issue.explanation
    if _CALIBRATED_PREFIX not in explanation:
        explanation = f"{_CALIBRATED_PREFIX} {explanation}"
    return issue.model_copy(
        update={
            "severity": Severity.LOW,
            "explanation": explanation,
        }
    )
