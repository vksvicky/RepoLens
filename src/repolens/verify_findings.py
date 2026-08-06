"""Opt-in Critical location re-verify (Phase 6.9). Never blocks report write."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig
from repolens.schema import Issue, Severity

_TAG = "[verify: location unconfirmed]"


def apply_verify_findings(
    root: Path,
    issues: list[Issue],
    deep: DeepConfig,
) -> list[Issue]:
    """Re-check Critical locations when ``verify_findings`` is enabled.

    Failures only annotate the issue; they never raise or abort the report.
    """
    if not deep.verify_findings:
        return issues

    from repolens.sarif import verify_issue_location

    out: list[Issue] = []
    for issue in issues:
        if issue.severity != Severity.CRITICAL:
            out.append(issue)
            continue
        try:
            loc = verify_issue_location(root, issue)
        except Exception:
            loc = None
        verified = loc is not None
        explanation = issue.explanation
        if not verified and _TAG not in explanation:
            explanation = f"{_TAG} {explanation}"
        out.append(
            issue.model_copy(
                update={
                    "locationVerified": verified,
                    "explanation": explanation,
                }
            )
        )
    return out
