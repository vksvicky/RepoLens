"""Markdown metrics table for a gate report."""

from __future__ import annotations

from repolens.schema import FindingReport, Severity


def format_collapsed_duplicates(report: FindingReport) -> str | None:
    """How scanner Critical/High rows were kept, suppressed, or dropped.

    ``None`` when the raw row count is missing or already matches the retained
    Critical and High counts.
    """
    unique = report.summary.critical + report.summary.high
    raw = report.rawCriticalHighCount
    if raw is None or raw <= unique:
        return None
    suppressed = sum(
        1
        for row in report.suppressedIssues
        if row.issue.severity in {Severity.CRITICAL, Severity.HIGH}
    )
    dropped = max(0, raw - unique - suppressed)
    parts: list[str] = []
    if suppressed:
        parts.append(f"{suppressed} suppressed")
    if dropped:
        parts.append(f"{dropped} not retained")
    detail = f" ({', '.join(parts)})" if parts else ""
    return f"{raw} tool rows evaluated → {unique} Critical/High retained{detail}"


def suppression_suffix(report: FindingReport) -> str:
    """How the suppressed rows were recorded, or empty when there are none."""
    rows = report.suppressedIssues
    if not rows:
        return ""
    if all(row.mechanism == "ignore_file" for row in rows):
        return " (via .repolens-ignore)"
    if all(row.mechanism == "disable_comment" for row in rows):
        return " (via inline disable comments)"
    return " (via .repolens-ignore or inline disable comments)"


def _clock(seconds: float | None) -> str:
    """Hours, minutes, and seconds. The raw second total stays in the JSON field."""
    from repolens.report import format_duration

    text = format_duration(seconds)
    if text is None:
        return ""
    return text.split(" (", 1)[0]


def _render_metrics_section(report: FindingReport) -> list[str]:
    """Glossary + band audit confidences (Phase 5.1) + Two-Lane counts (6.11)."""
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
    if report.suppressedIssues:
        lines.append(
            f"| Suppressed | {len(report.suppressedIssues)} | "
            f"Reviewed and excluded from the gate{suppression_suffix(report)} |"
        )
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
            f"| Critical/High rows | {collapsed} | Scanner rows at Critical or High, "
            "then how many were kept, suppressed, or not retained |"
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


_CLOUD_PROVIDERS = frozenset(
    {"openai", "anthropic", "gemini", "vertex", "bedrock", "deepseek"}
)


def _data_boundary(provider: str | None) -> str:
    name = (provider or "").strip().lower()
    if name == "ollama":
        return (
            "Local model. Source text was not sent to a cloud model API. "
            "Scanner tools may still contact their own services."
        )
    if name in _CLOUD_PROVIDERS:
        return (
            f"Model calls used `{provider}`. This run was not air-gapped. "
            "Scanner tools may still contact their own services."
        )
    if name == "openai_compatible":
        return (
            "Model calls used the configured OpenAI-compatible endpoint. "
            "Treat this as air-gapped only when that endpoint is on this machine."
        )
    if name:
        return (
            f"Model calls used `{provider}`. "
            "Confirm that endpoint before treating this run as air-gapped."
        )
    return "Model provider was not recorded."


def _render_audit_ledger(report: FindingReport) -> list[str]:
    """Four-line proof of how the review was run."""
    prov = report.provenance
    version = prov.repoLensVersion if prov and prov.repoLensVersion else "unknown"
    lines = ["", "---", "", "### Audit Ledger", "", f"- **Engine:** RepoLens {version}"]
    if prov is None:
        lines.append("- **Execution:** not recorded")
        lines.append("- **Data boundary:** Model provider was not recorded.")
        lines.append("- **Tree:** Git commit was not recorded.")
        lines.append("")
        return lines
    bits: list[str] = []
    if prov.fastBrainSeconds is not None:
        bits.append(f"Fast Brain {_clock(prov.fastBrainSeconds)}")
    if prov.llmSeconds is not None:
        model = prov.model or "the configured model"
        bit = f"Slow Brain {_clock(prov.llmSeconds)} via `{model}`"
        waited = prov.queueWaitSeconds or 0
        if waited > 0:
            generating = max(0.0, prov.llmSeconds - waited)
            bit += f" (queued {_clock(waited)}, generating {_clock(generating)})"
        bits.append(bit)
    lines.append(
        "- **Execution:** " + (" | ".join(bits) if bits else "times were not recorded")
    )
    lines.append(f"- **Data boundary:** {_data_boundary(prov.provider)}")
    if prov.gitSha:
        lines.append(f"- **Tree:** commit `{prov.gitSha}`")
    else:
        lines.append("- **Tree:** Git commit was not recorded.")
    lines.append("")
    return lines
