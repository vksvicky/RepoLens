"""Standard AI / LLM output disclaimer for reports and docs."""

from __future__ import annotations

DISCLAIMER_TITLE = "Disclaimer"
OFFERING_TITLE = "About"

CYCLERUNCODE_CLUB_URL = "https://cycleruncode.club"
CYCLERUNCODE_CLUB_NAME = "CycleRunCode Club"

# Keep paragraphs short and report-friendly.
DISCLAIMER_PARAGRAPHS: tuple[str, ...] = (
    (
        "Findings, scores, remediation suggestions, diagrams, and code examples "
        "produced by RepoLens may be generated or assisted by artificial "
        "intelligence (AI) / large language models (LLMs), deterministic "
        "heuristics, and optional third-party scanners. That output can be "
        "incomplete, incorrect, outdated, or unsuitable for your environment."
    ),
    (
        "RepoLens and its authors (including contributors and maintainers) "
        "provide the software and its outputs **as is**, without warranty of "
        "any kind, express or implied. You remain solely responsible for "
        "reviewing results, validating fixes, assessing risk, and deciding "
        "what to ship. The authors accept **no liability** for loss, damage, "
        "security incidents, or other consequences arising from reliance on "
        "AI/LLM-generated or tool-assisted advice."
    ),
    (
        "This report is **not** a certification, penetration test, legal "
        "opinion, or professional security audit engagement. Use at your own "
        "risk."
    ),
)


def offering_markdown_lines() -> list[str]:
    """Attribution: RepoLens is part of the CycleRunCode Club offering."""
    return [
        f"## {OFFERING_TITLE}",
        "",
        (
            "RepoLens is part of the "
            f"**[{CYCLERUNCODE_CLUB_NAME}]({CYCLERUNCODE_CLUB_URL})** offering — "
            "teaching playbooks and tools for structured code review, security, "
            "and shipping with confidence. Report prose uses British English."
        ),
        "",
    ]


def disclaimer_markdown_lines() -> list[str]:
    """Markdown section lines for gate review reports (offering + disclaimer)."""
    lines: list[str] = offering_markdown_lines()
    lines.extend([f"## {DISCLAIMER_TITLE}", ""])
    for para in DISCLAIMER_PARAGRAPHS:
        lines.append(para)
        lines.append("")
    return lines
