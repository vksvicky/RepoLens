"""CI triage routing: when/whether the LLM runs, and on which files (Phase 6.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from repolens.config import CiConfig
from repolens.schema import FindingReport, Issue, Severity

IssueSource = Literal["scanner", "heuristic", "llm"]

_SCANNER_CATEGORIES = frozenset(
    {"gitleaks", "semgrep", "osv", "trivy", "checkov"}
)
_SEVERITY_ORDER = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}
_FLOOR_ALIASES = {
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
}


@dataclass
class TriagePlan:
    """Outcome of triage routing before the LLM stage."""

    should_invoke_llm: bool
    llm_bypassed: bool
    pack_files: list[str]
    hit_issues: list[Issue] = field(default_factory=list)
    triage_hits: int = 0
    truncated: bool = False
    notes: list[str] = field(default_factory=list)


def _norm_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _meets_floor(issue: Issue, floor: str) -> bool:
    key = (floor or "HIGH").strip().upper()
    floor_sev = _FLOOR_ALIASES.get(key, Severity.HIGH)
    return _SEVERITY_ORDER[issue.severity] >= _SEVERITY_ORDER[floor_sev]


def infer_issue_source(issue: Issue) -> IssueSource:
    """Best-effort source tag for gating and provenance."""
    if issue.source in {"scanner", "heuristic", "llm"}:
        return issue.source  # type: ignore[return-value]
    cat = (issue.category or "").strip().lower()
    if cat in _SCANNER_CATEGORIES or any(m in cat for m in _SCANNER_CATEGORIES):
        return "scanner"
    if cat.startswith("heuristic.") or cat.startswith("pack."):
        return "heuristic"
    return "llm"


def stamp_issue_sources(
    issues: list[Issue],
    *,
    default_llm: bool = False,
) -> list[Issue]:
    """Fill missing ``source`` from category heuristics."""
    out: list[Issue] = []
    for issue in issues:
        if issue.source in {"scanner", "heuristic", "llm"}:
            out.append(issue)
            continue
        cat = (issue.category or "").strip().lower()
        if cat in _SCANNER_CATEGORIES or any(m in cat for m in _SCANNER_CATEGORIES):
            out.append(issue.model_copy(update={"source": "scanner"}))
        elif cat.startswith("heuristic.") or cat.startswith("pack."):
            out.append(issue.model_copy(update={"source": "heuristic"}))
        elif default_llm:
            out.append(issue.model_copy(update={"source": "llm"}))
        else:
            out.append(issue)
    return out


def triage_llm_plan(
    scanner_issues: list[Issue],
    *,
    available_files: list[str],
    config: CiConfig,
    changed_files: list[str] | None = None,
    heuristic_issues: list[Issue] | None = None,
    include_heuristics: bool = False,
) -> TriagePlan:
    """Decide whether to invoke the LLM and which files enter the pack.

    When ``triage_routing`` is off, the full ``available_files`` pack is kept
    and the LLM may run (caller still applies dry-run / scanners-only).

    Phase 6.11: optional Fast Brain heuristic hits can join scanner hits when
    ``include_heuristics`` is True (fail-on remains scanner-preferring in CI).
    """
    available = [_norm_path(p) for p in available_files]
    available_set = set(available)

    if not config.triage_routing:
        return TriagePlan(
            should_invoke_llm=True,
            llm_bypassed=False,
            pack_files=list(available),
            notes=[],
        )

    hits: list[Issue] = []
    changed_set = (
        {_norm_path(p) for p in changed_files} if changed_files is not None else None
    )
    pool: list[Issue] = list(scanner_issues)
    if include_heuristics and heuristic_issues:
        pool.extend(heuristic_issues)
    for issue in pool:
        src = infer_issue_source(issue)
        if src == "scanner":
            pass
        elif include_heuristics and src == "heuristic":
            pass
        else:
            continue
        if not _meets_floor(issue, config.severity_floor):
            continue
        path = _norm_path(issue.file)
        if changed_set is not None and path not in changed_set:
            continue
        hits.append(issue)

    if not hits:
        if config.llm_on_clean_diff:
            return TriagePlan(
                should_invoke_llm=True,
                llm_bypassed=False,
                pack_files=list(available),
                triage_hits=0,
                notes=["triage: llm_on_clean_diff — LLM allowed despite clean scanners"],
            )
        clean_what = (
            "scanners/heuristics" if include_heuristics else "scanners"
        )
        return TriagePlan(
            should_invoke_llm=False,
            llm_bypassed=True,
            pack_files=[],
            triage_hits=0,
            notes=[f"triage: {clean_what} clean at severity floor — LLM bypassed"],
        )

    # Preserve first-seen file order from hits, then intersect available pack
    ordered: list[str] = []
    seen: set[str] = set()
    for issue in hits:
        path = _norm_path(issue.file)
        if path in seen:
            continue
        seen.add(path)
        if path in available_set or not available_set:
            ordered.append(path)
        elif path not in available_set:
            # Still include hit path so pack is not empty when inventory differs
            ordered.append(path)

    truncated = False
    notes: list[str] = []
    max_files = max(1, int(config.max_triage_files))
    if len(ordered) > max_files:
        truncated = True
        notes.append(
            f"triage: truncated pack to max_triage_files={max_files} "
            f"(had {len(ordered)} hit file(s))"
        )
        ordered = ordered[:max_files]

    return TriagePlan(
        should_invoke_llm=True,
        llm_bypassed=False,
        pack_files=ordered,
        hit_issues=hits,
        triage_hits=len(hits),
        truncated=truncated,
        notes=notes,
    )


def select_pack_entries(files: list, pack_files: list[str]) -> list:
    """Filter inventory ``FileEntry`` list to triage pack paths."""
    want = {_norm_path(p) for p in pack_files}
    selected = [f for f in files if _norm_path(getattr(f, "relative", str(f))) in want]
    if selected:
        return selected
    # Fall back: keep original order filtered loosely by suffix match
    return [
        f
        for f in files
        if any(_norm_path(getattr(f, "relative", "")) == p for p in pack_files)
    ]


def fail_on_triggered(
    report: FindingReport,
    fail_on: str | None,
    *,
    scanner_only: bool = False,
) -> bool:
    """True when any finding meets the severity threshold.

    When ``scanner_only`` is True (CI default), LLM/heuristic rows do not fail
    the gate — scanners remain the production gate.
    """
    if not fail_on:
        return False
    order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    key = fail_on.upper()
    if key not in order:
        raise ValueError(
            f"Invalid --fail-on severity {fail_on!r}; use CRITICAL|HIGH|MEDIUM|LOW"
        )
    threshold = order[key]
    for issue in report.issues:
        if scanner_only and infer_issue_source(issue) != "scanner":
            continue
        if order[issue.severity.value] >= threshold:
            return True
    return False
