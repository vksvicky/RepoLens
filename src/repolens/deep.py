"""Deep multi-pass planner, file budgeting, merge/dedupe, and prompt builder.

Char budgeting uses ``FileEntry.size`` (bytes) as a character-cost estimate so
planning does not read file contents. Callers that later pack prompts should
still use ``read_excerpt`` (or the same size estimate) consistently with this
budget so selected files fit the pass cap.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

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
_COVERAGE_LINE_SHAPE = (
    "coverage:<id>: N/A — <one fact that is true in this repository>"
)
_TESTING_CATEGORIES = frozenset(
    {"arch.testing", "testing.missing_tests", "testing.scenario_gap"}
)
_GITIGNORE_SECRET_CATEGORIES = frozenset(
    {"sec.repo_hygiene_secrets", "sec.secrets", "heuristic.gitignore_secrets"}
)
_CI_PIPELINE_NAMES = frozenset(
    {
        ".gitlab-ci.yml",
        ".gitlab-ci.yaml",
        "azure-pipelines.yml",
        "azure-pipelines.yaml",
        "bitbucket-pipelines.yml",
        ".travis.yml",
        "appveyor.yml",
        ".drone.yml",
        "woodpecker.yml",
    }
)


def coverage_checklist_tail(coverage_ids: Iterable[str]) -> str:
    """Restate the checklist after the source files so a large pack cannot bury it."""
    ids = [cid for cid in coverage_ids if cid]
    if not ids:
        return ""
    lines = [
        "",
        "## Coverage checklist (required before JSON)",
        "Account for every id below. For an id with no finding, add one line",
        "in this shape, using that id and a fact from this repository:",
        _COVERAGE_LINE_SHAPE,
        "Do not copy a fact from another repository.",
        "A line without the coverage: prefix, or a reason that says “not reviewed”,",
        "does not count and lowers the gate.",
    ]
    lines.extend(f"- {cid}" for cid in ids)
    return "\n".join(lines)


def coverage_closure_prompt(missed_ids: Iterable[str]) -> str:
    """Ask only for checklist ids the earlier passes left unanswered."""
    ids = [cid for cid in missed_ids if cid]
    lines = [
        "Coverage closure. Earlier passes left these checklist ids unanswered.",
        "For each id, either emit an issue whose category is that id, or one",
        "line in this shape, using that id and a fact from this repository:",
        _COVERAGE_LINE_SHAPE,
        "Do not copy a fact from another repository.",
        "A reason that says 'not reviewed' is rejected and the id stays missed.",
        "Return FindingReport JSON only.",
        "",
    ]
    lines.extend(f"- {cid}" for cid in ids)
    lines.append("")
    lines.append(BRITISH_ENGLISH_INSTRUCTION)
    return "\n".join(lines)


@dataclass(frozen=True)
class DeepPass:
    name: str
    rule_ids: list[str]
    coverage_ids: list[str]
    files: list[FileEntry]
    pack_mode: str = "full"  # full | outline | hybrid
    file_pack_modes: dict[str, str] = field(default_factory=dict)


_P1_PATH_HINTS = (
    "auth",
    "secret",
    "password",
    "credential",
    "crypto",
    "jwt",
    "oauth",
    "session",
    "security",
    "tls",
    "ssl",
    "sql",
    "exec",
    "shell",
    "environ",
    "permission",
    "rbac",
    "firewall",
    ".env",
)
_P2_PATH_HINTS = (
    "error",
    "except",
    "retry",
    "timeout",
    "backoff",
    "lock",
    "thread",
    "async",
    "pool",
    "queue",
    "transaction",
    "cleanup",
    "recover",
    "health",
    "circuit",
    "resilien",
)


def estimate_outline_chars(entry: FileEntry) -> int:
    """Char-cost estimate for an outline pack without reading the file.

    Outlines are typically far smaller than raw bodies; using ``entry.size``
    would empty a P3 budget after a handful of large modules.
    """
    approx_lines = max(1, entry.size // 40)
    return max(80, min(entry.size, approx_lines * 30 // 8))


def budget_files(
    entries: Sequence[FileEntry],
    *,
    max_chars: int,
    cost_fn: Callable[[FileEntry], int] | None = None,
) -> list[FileEntry]:
    """Greedily select files in order without exceeding ``max_chars``.

    Default cost per file is ``FileEntry.size`` (documented size-based estimate).
    Files larger than the remaining budget are skipped (later smaller files
    may still fit).
    """
    if max_chars <= 0:
        return []
    measure = cost_fn or (lambda entry: entry.size)
    selected: list[FileEntry] = []
    used = 0
    for entry in entries:
        cost = int(measure(entry))
        if cost > max_chars:
            continue
        if used + cost > max_chars:
            continue
        selected.append(entry)
        used += cost
    return selected


def compact_pass_summary(
    report: FindingReport, *, max_chars: int = 800
) -> str:
    """≤~200-token summary of findings for the next deep pass."""
    lines = ["Confirmed findings from the prior Slow Brain pass:"]
    for issue in report.issues[:12]:
        sev = getattr(issue.severity, "value", issue.severity)
        lines.append(f"- [{sev}] {issue.title} ({issue.file}:{issue.line})")
    if not report.issues:
        lines.append("- (no findings)")
    covered = [
        gap for gap in report.durabilityGaps if gap.startswith("coverage:")
    ][:8]
    if covered:
        lines.append("Coverage notes:")
        lines.extend(f"- {gap}" for gap in covered)
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _path_hint_score(relative: str, hints: tuple[str, ...]) -> int:
    lowered = relative.lower().replace("\\", "/")
    return sum(1 for hint in hints if hint in lowered)


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
            continue
        ordered.append(entry)
        seen.add(entry.relative)
    return ordered


def _order_for_band(
    entries: Sequence[FileEntry],
    *,
    band: str,
    hot_paths: Iterable[str],
    adaptive_paths: Iterable[str],
) -> list[FileEntry]:
    from repolens.pack_sniff import is_demoted_asset, sniff_score

    if band in {"p1", "p2"}:
        entries = [e for e in entries if not is_demoted_asset(e.relative)]
    base = _order_entries(
        entries, hot_paths=hot_paths, adaptive_paths=adaptive_paths
    )
    if band not in {"p1", "p2"}:
        return base

    def sort_key(entry: FileEntry) -> tuple[int, int, str]:
        return (
            -sniff_score(band, entry),
            entry.priority_band,
            entry.relative,
        )

    return sorted(base, key=sort_key)


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
    max_passes: int | None = None,
    role_packs: bool = False,
) -> list[DeepPass]:
    """Plan band-ordered deep passes from enabled rules for ``mode``.

    ``max_passes`` caps how many band passes run (1 = first band only, e.g. P1
    for ``review``). ``None`` or ``<= 0`` keeps the full mode band list.

    When ``role_packs`` is true, each band gets its own ordered budget and P3
    uses outline-cost estimates with ``pack_mode=\"outline\"``.
    """
    bands = _MODE_BANDS.get(mode)
    if bands is None:
        raise ValueError(f"Unknown mode: {mode}")
    if max_passes is not None and max_passes > 0:
        bands = bands[:max_passes]

    shared = None
    if not role_packs:
        ordered_files = _order_entries(
            entries, hot_paths=hot_paths, adaptive_paths=adaptive_paths
        )
        shared = budget_files(ordered_files, max_chars=chars_per_pass)

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
        if role_packs:
            ordered = _order_for_band(
                entries,
                band=band,
                hot_paths=hot_paths,
                adaptive_paths=adaptive_paths,
            )
            if band == "p3":
                packed = budget_files(
                    ordered,
                    max_chars=chars_per_pass,
                    cost_fn=estimate_outline_chars,
                )
                pack_mode = "outline"
            else:
                packed = budget_files(ordered, max_chars=chars_per_pass)
                pack_mode = "full"
        else:
            packed = list(shared or [])
            pack_mode = "full"
        passes.append(
            DeepPass(
                name=band,
                rule_ids=rule_ids,
                coverage_ids=cov_ids,
                files=list(packed),
                pack_mode=pack_mode,
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


def _normalise_repo_path(file: str) -> str:
    path = (file or "").replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    return path


def _is_ci_pipeline(path: str) -> bool:
    """True for a CI pipeline definition in any common host, not a test module."""
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    if name in _CI_PIPELINE_NAMES or name.startswith("jenkinsfile"):
        return True
    markers = (
        ".github/workflows/",
        ".circleci/",
        ".buildkite/",
    )
    return any(
        lowered.startswith(marker) or f"/{marker}" in f"/{lowered}" for marker in markers
    )


def _is_gitignore_secret_claim(path: str, category: str) -> bool:
    """Fast Brain measures secret patterns in any repository's .gitignore."""
    return path.rsplit("/", 1)[-1] == ".gitignore" and category in _GITIGNORE_SECRET_CATEGORIES


def is_unmeasured_model_claim(issue: Issue) -> bool:
    """True when the model is restating a measurement or a CI pipeline file.

    Complexity and ``heuristic.*`` / ``pack.*`` come from Fast Brain. A CI
    pipeline file is not a unit-test module. Secret patterns in ``.gitignore``
    are measured by Fast Brain for every repository.
    """
    cat = (issue.category or "").strip().lower()
    path = _normalise_repo_path(issue.file)
    if cat == "quality.complexity":
        return True
    if cat.startswith("heuristic.") or cat.startswith("pack."):
        return True
    if cat in _TESTING_CATEGORIES and _is_ci_pipeline(path):
        return True
    return _is_gitignore_secret_claim(path, cat)


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
        issue_stream.extend(
            issue.model_copy(update={"source": "llm"})
            for issue in part.issues
            if not is_unmeasured_model_claim(issue)
        )

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
    *,
    pack_ids: list[str] | None = None,
) -> str:
    """Concatenate enabled rule bodies for the pass plus the coverage contract."""
    from repolens.packs.registry import pack_playbook_sections

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
    for label, content in pack_playbook_sections(pack_ids or []):
        sections.append(f"## Playbook: {label}")
        sections.append(content)
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
