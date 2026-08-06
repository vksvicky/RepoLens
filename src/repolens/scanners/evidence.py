"""Format scanner findings for LLM prompt context (Phase 6.1)."""

from __future__ import annotations

from repolens.schema import Issue

_MAX_ITEMS = 40
_MAX_CHARS = 12_000


def format_scanner_evidence_for_prompt(issues: list[Issue]) -> str:
    """Compact, evidence-first block for deep / single-shot prompts."""
    if not issues:
        return ""
    lines = [
        "## Scanner evidence (deterministic — prefer these facts over speculation)",
        "Do not invent dependency graphs or CVE reachability beyond this list.",
        "Use these findings as ground truth; explain impact and remediation in context.",
        "",
    ]
    for issue in issues[:_MAX_ITEMS]:
        lines.append(
            f"- [{issue.severity.value}/{issue.category}] "
            f"{issue.file}:{issue.line} — {issue.title}"
        )
    if len(issues) > _MAX_ITEMS:
        lines.append(f"- … and {len(issues) - _MAX_ITEMS} more scanner finding(s)")
    text = "\n".join(lines)
    if len(text) > _MAX_CHARS:
        return text[:_MAX_CHARS] + "\n…(truncated)"
    return text
