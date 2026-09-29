"""Markdown metrics table for a gate report."""

from __future__ import annotations

from repolens.schema import FindingReport


def _clock(seconds: float | None) -> str:
    """Hours, minutes, and seconds. The raw second total stays in the JSON field."""
    from repolens.report import format_duration

    text = format_duration(seconds)
    if text is None:
        return ""
    return text.split(" (", 1)[0]


def _render_metrics_section(report: FindingReport) -> list[str]:
    """Glossary + band audit confidences (Phase 5.1) + Two-Lane counts (6.11)."""
    from repolens.report import format_collapsed_duplicates

    has_bands = (
        report.securityAuditConfidence is not None
        or report.architectureAuditConfidence is not None
        or report.reliabilityAuditConfidence is not None
    )
    prov = report.provenance
    has_fast_brain = prov is not None and prov.fastBrainFiles is not None
    if not has_bands and not has_fast_brain:
        return []
    lines = [
        "## Metrics",
        "",
        (
            "**Gate** = adequacy of *this review package* (findings + checklist "
            "coverage + scanners) for a go/no-go style decision — **not** "
            "“% secure” or an architecture grade. Band audits score checklist "
            "honesty per P1/`sec.*`, P2/`rel.*`, P3/`arch.*`. See FAQ: "
            "*What do report metrics mean?*"
        ),
        "",
        "| Metric | Value | Meaning |",
        "|--------|-------|---------|",
        (
            f"| Gate confidence | {report.confidence}% | Lowest band, then a penalty "
            "for each missed checklist id. [Why](#why-a-score-is-low) · "
            "[Checklist](#checklist) |"
        ),
    ]
    counts = report.summary
    for label, count, meaning in (
        (
            "Critical",
            counts.critical,
            "Scanner and Fast Brain findings at Critical. Model notes are not included.",
        ),
        (
            "High",
            counts.high,
            "Scanner and Fast Brain findings at High. Model notes are not included.",
        ),
        (
            "Medium",
            counts.medium,
            "Scanner and Fast Brain findings at Medium. These do not change the percentages.",
        ),
        (
            "Low",
            counts.low,
            "Scanner and Fast Brain findings at Low. These do not change the percentages.",
        ),
    ):
        lines.append(f"| {label} | {count} | {meaning} |")
    if report.durationSeconds is not None:
        lines.append(
            f"| Duration | {_clock(report.durationSeconds)} | Wall-clock time for "
            "this review |"
        )
    if prov is not None and prov.fastBrainFiles is not None:
        lines.append(
            f"| Fast Brain files | {prov.fastBrainFiles} | Inventory used for "
            "whole-tree heuristics (Phase 6.11 Two-Lane) |"
        )
        if prov.llmPackFiles is not None:
            lines.append(
                f"| LLM pack files | {prov.llmPackFiles} | Files sent to the model "
                "(0 if bypassed / scanners-only) |"
            )
        if prov.fastBrainSeconds is not None:
            lines.append(
                f"| Fast Brain time | {_clock(prov.fastBrainSeconds)} | Wall time "
                "for whole-tree heuristics |"
            )
        if prov.llmSeconds is not None:
            lines.append(
                f"| Slow Brain time | {_clock(prov.llmSeconds)} | Wall time for "
                "LLM / deep analysis |"
            )
    if report.securityAuditConfidence is not None:
        lines.append(
            f"| Security audit confidence | {report.securityAuditConfidence}% | "
            "Security checklist plus Critical/High security findings. "
            "[Why](#why-a-score-is-low) |"
        )
    if report.reliabilityAuditConfidence is not None:
        lines.append(
            f"| Reliability audit confidence | {report.reliabilityAuditConfidence}% | "
            "Reliability checklist plus Critical/High reliability findings. "
            "[Why](#why-a-score-is-low) |"
        )
    if report.architectureAuditConfidence is not None:
        lines.append(
            f"| Architecture audit confidence | {report.architectureAuditConfidence}% | "
            "Architecture checklist plus Critical/High architecture findings. "
            "[Why](#why-a-score-is-low) |"
        )
    collapsed = format_collapsed_duplicates(report)
    if collapsed is not None:
        lines.append(
            f"| Duplicates merged | {collapsed} | Same advisory reported by "
            "more than one scanner or the model, before those rows were combined |"
        )
    if has_bands:
        lines.extend(
            [
                (
                    "| Checklist | (below) | [Checklist](#checklist): answered, "
                    "does not apply, or not answered |"
                ),
                "",
                "### How these % are calculated",
                "",
                "- **Gate** is the lowest band, then a penalty for missed checklist ids.",
                "- **Security, reliability, and architecture** drop when that band has "
                "a missed checklist id or a Critical/High finding.",
                "- Medium and Low findings do not change these percentages.",
                "- Each unanswered question is explained under [Checklist](#checklist).",
                "- Full arithmetic: RepoLens `docs/faq.md` → *What do report metrics mean?*",
                "",
            ]
        )
        from repolens.metrics import low_audit_explanations

        reasons = list(report.scoreNotes) or low_audit_explanations(report)
        if reasons:
            lines.extend(
                [
                    "### Why a score is low",
                    "",
                    "Shown when a band or the gate is under 70%. Medium and Low findings "
                    "do not change these percentages. Each unanswered question is "
                    "explained under [Checklist](#checklist).",
                    "",
                ]
            )
            lines.extend(f"- {reason}" for reason in reasons)
            lines.append("")
    else:
        lines.append("")
    return lines
