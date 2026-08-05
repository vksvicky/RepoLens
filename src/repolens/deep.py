"""Deep multi-pass planner, file budgeting, merge/dedupe, and prompt builder.

Char budgeting uses ``FileEntry.size`` (bytes) as a character-cost estimate so
planning does not read file contents. Callers that later pack prompts should
still use ``read_excerpt`` (or the same size estimate) consistently with this
budget so selected files fit the pass cap.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from repolens.coverage import coverage_ids_for_pass
from repolens.inventory import FileEntry
from repolens.prose import BRITISH_ENGLISH_INSTRUCTION
from repolens.rules.registry import Rule
from repolens.schema import FindingReport, Issue, Summary

_MODE_BANDS: dict[str, tuple[str, ...]] = {
    "sentinel": ("p1",),
    "architecture": ("p3",),
    "review": ("p1", "p2", "p3"),
}

_COVERAGE_CONTRACT = (
    "Coverage contract: for each coverage id listed below, either emit one or "
    "more FindingReport issues that address it, or add a durabilityGaps entry "
    "of the form `coverage:<id>: N/A — <reason>`."
)


@dataclass(frozen=True)
class DeepPass:
    name: str
    rule_ids: list[str]
    coverage_ids: list[str]
    files: list[FileEntry]


def budget_files(entries: Sequence[FileEntry], *, max_chars: int) -> list[FileEntry]:
    """Greedily select files in order without exceeding ``max_chars``.

    Cost per file is ``FileEntry.size`` (documented size-based estimate).
    Files larger than the remaining budget are skipped (later smaller files
    may still fit).
    """
    if max_chars <= 0:
        return []
    selected: list[FileEntry] = []
    used = 0
    for entry in entries:
        cost = entry.size
        if cost > max_chars:
            continue
        if used + cost > max_chars:
            continue
        selected.append(entry)
        used += cost
    return selected


def _order_entries(
    entries: Sequence[FileEntry],
    *,
    hot_paths: Iterable[str],
    adaptive_paths: Iterable[str],
) -> list[FileEntry]:
    preferred = set(hot_paths) | set(adaptive_paths)
    by_rel = {e.relative: e for e in entries}
    ordered: list[FileEntry] = []
    seen: set[str] = set()

    # Preserve hot then adaptive order when both provided; union prefers first-seen.
    for rel in list(hot_paths) + list(adaptive_paths):
        if rel in seen:
            continue
        entry = by_rel.get(rel)
        if entry is None:
            continue
        ordered.append(entry)
        seen.add(rel)

    for entry in entries:
        if entry.relative in seen:
            continue
        if entry.relative in preferred:
            # Already handled above; keep for safety if path only in preferred set
            continue
        ordered.append(entry)
        seen.add(entry.relative)
    return ordered


def _enabled_by_band(rules: Sequence[Rule], band: str) -> list[Rule]:
    band_norm = band.lower()
    return [r for r in rules if r.enabled and r.band.lower() == band_norm]


def plan_deep_passes(
    mode: str,
    *,
    full_audit: bool,
    entries: Sequence[FileEntry],
    hot_paths: Iterable[str],
    adaptive_paths: Iterable[str],
    chars_per_pass: int,
    rules: list[Rule],
) -> list[DeepPass]:
    """Plan band-ordered deep passes from enabled rules for ``mode``."""
    bands = _MODE_BANDS.get(mode)
    if bands is None:
        raise ValueError(f"Unknown mode: {mode}")

    ordered_files = _order_entries(
        entries, hot_paths=hot_paths, adaptive_paths=adaptive_paths
    )
    packed = budget_files(ordered_files, max_chars=chars_per_pass)

    passes: list[DeepPass] = []
    for band in bands:
        band_rules = _enabled_by_band(rules, band)
        if not band_rules:
            continue
        rule_ids = [r.id for r in band_rules]
        cov_ids = coverage_ids_for_pass(
            band,
            full_audit=full_audit,
            enabled_rule_ids=rule_ids,
        )
        passes.append(
            DeepPass(
                name=band,
                rule_ids=rule_ids,
                coverage_ids=cov_ids,
                files=list(packed),
            )
        )
    return passes


def _dedupe_issues(issues: Iterable[Issue]) -> list[Issue]:
    out: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue.file, issue.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


def _combine_gaps(parts: Sequence[FindingReport]) -> list[str]:
    gaps: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for gap in part.durabilityGaps:
            if gap in seen:
                continue
            seen.add(gap)
            gaps.append(gap)
    return gaps


def _min_confidence(parts: Sequence[FindingReport]) -> int:
    confidences = [
        part.confidence for part in parts if part.issues or part.durabilityGaps
    ]
    return min(confidences) if confidences else 0


def merge_reports(
    parts: list[FindingReport],
    heuristic_issues: list[Issue],
) -> FindingReport:
    """Merge LLM pass reports + heuristics; dedupe by (file, title).

    Confidence is the minimum across non-empty parts (parts with no issues and
    no durabilityGaps are ignored). When no such parts remain, confidence is 0.
    """
    issue_stream: list[Issue] = list(heuristic_issues)
    for part in parts:
        issue_stream.extend(part.issues)

    scores = next((p.scores for p in parts if p.scores is not None), None)
    scanner_runs = [run for part in parts for run in part.scannerRuns]

    report = FindingReport(
        confidence=_min_confidence(parts),
        summary=Summary(),
        issues=_dedupe_issues(issue_stream),
        durabilityGaps=_combine_gaps(parts),
        scores=scores,
        scannerRuns=scanner_runs,
    )
    report.summary = report.recount_summary()
    return report


def build_deep_prompt(
    deep_pass: DeepPass,
    rules: list[Rule],
    coverage_ids: Iterable[str],
) -> str:
    """Concatenate enabled rule bodies for the pass plus the coverage contract."""
    by_id = {r.id: r for r in rules}
    sections: list[str] = [
        f"Deep pass: {deep_pass.name}",
        f"Rule ids: {', '.join(deep_pass.rule_ids)}",
        "",
    ]
    for rule_id in deep_pass.rule_ids:
        rule = by_id.get(rule_id)
        if rule is None or not rule.enabled:
            continue
        sections.append(f"## Rule: {rule.title} ({rule.id})")
        sections.append(rule.body)
        sections.append("")

    cov_list = list(coverage_ids)
    sections.append("## Coverage ids")
    sections.append(_COVERAGE_CONTRACT)
    if cov_list:
        for cov_id in cov_list:
            sections.append(f"- {cov_id}")
    else:
        sections.append("(none)")
    sections.append("")
    sections.append(BRITISH_ENGLISH_INSTRUCTION)
    sections.append(
        "Analyse using the rules and coverage contract. Return FindingReport JSON only."
    )
    return "\n".join(sections)
