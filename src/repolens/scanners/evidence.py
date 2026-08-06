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
        "Use these findings as ground truth; explain impact and remediation in context.",
        "SCA / dependencies (mandatory):",
        "- Vulnerable packages and CVE/GHSA IDs come only from scanner rows below "
        "(OSV/Trivy). Do not invent a dependency graph.",
        "- Do not reason over lockfiles (`package-lock.json`, `poetry.lock`, "
        "`Cargo.lock`, etc.) to invent edges or prod vs dev exposure.",
        "- Do not claim reachability or “hits production” unless a scanner field "
        "explicitly states it. If unsure, say reachability was not assessed.",
        "- Your job for SCA is remediation advice from the listed facts — not discovery.",
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
