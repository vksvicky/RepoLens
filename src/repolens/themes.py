"""Phase 5.2 — Core + Extended theme registry and report breakdown helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal

from repolens.coverage import CoverageEntry, CoverageMatrix, CoverageResult, load_coverage_matrix
from repolens.schema import Issue, ThemeEntry

# Deprecated coverage ids → canonical theme ids (temporary alias acceptance).
COVERAGE_ID_ALIASES: dict[str, str] = {
    "sec.secrets": "sec.repo_hygiene_secrets",
    "sec.deps_config": "sec.deps_supply_chain",
}

# Heuristic issue categories → theme coverage ids.
HEURISTIC_TO_THEME: dict[str, str] = {
    "heuristic.mega_file": "arch.structure_size",
    "heuristic.sibling_duplication": "arch.duplication",
    "heuristic.gitignore_secrets": "sec.repo_hygiene_secrets",
    "heuristic.scripts_hygiene": "arch.dead_code",
    "heuristic.todo_density": "arch.dead_code",
    "heuristic.ci_gaps": "arch.ci_durability",
}

CORE_THEME_IDS: frozenset[str] = frozenset(
    {
        "arch.structure_size",
        "arch.readability_complexity",
        "arch.duplication",
        "arch.dead_code",
        "arch.consistency_style",
        "sec.repo_hygiene_secrets",
        "sec.injection",
        "sec.xss_csrf",
        "sec.authn_authz",
        "sec.data_exposure",
        "sec.deps_supply_chain",
        "sec.transport_tls",
        "sec.crypto_deser",
        "sec.input_validation",
        "rel.edge_cases",
        "rel.concurrency",
        "rel.error_recovery",
        "rel.performance",
    }
)

EXTENDED_THEME_IDS: frozenset[str] = frozenset(
    {
        "arch.database",
        "arch.api",
        "arch.frontend",
        "arch.a11y",
        "arch.testing",
        "arch.observability",
        "arch.ci_durability",
        "arch.iac_cloud",
        "arch.i18n",
        "arch.pwa",
        "arch.licensing",
        "arch.scalability",
        "sec.config_env",
        "sec.privacy_pii",
        "sec.upload_path",
        "sec.session_cookies",
        "sec.rate_abuse",
        "sec.build_release",
        "arch.documentation",
    }
)


def canonicalize_coverage_id(cov_id: str) -> str:
    return COVERAGE_ID_ALIASES.get(cov_id, cov_id)


def theme_id_for_category(category: str) -> str | None:
    cat = category.strip()
    if cat in HEURISTIC_TO_THEME:
        return HEURISTIC_TO_THEME[cat]
    if cat in CORE_THEME_IDS or cat in EXTENDED_THEME_IDS:
        return cat
    canon = canonicalize_coverage_id(cat)
    if canon in CORE_THEME_IDS or canon in EXTENDED_THEME_IDS:
        return canon
    return None


def _entry_map(matrix: CoverageMatrix | None = None) -> dict[str, CoverageEntry]:
    matrix = matrix or load_coverage_matrix()
    return {e.id: e for e in matrix.entries}


def _status_for(
    cov_id: str,
    coverage: CoverageResult,
) -> tuple[str, str]:
    if cov_id in coverage.covered:
        return "covered", ""
    if cov_id in coverage.na:
        return "na", coverage.na[cov_id]
    if cov_id in coverage.missed:
        return "missed", ""
    return "missed", ""


def _count_findings(theme_id: str, issues: Sequence[Issue]) -> int:
    count = 0
    for issue in issues:
        mapped = theme_id_for_category(issue.category)
        if mapped == theme_id:
            count += 1
            continue
        # Also count when theme id appears in issue text (LLM categories).
        hay = f"{issue.category} {issue.title} {issue.explanation}".lower()
        if theme_id.lower() in hay:
            count += 1
    return count


def build_theme_breakdown(
    coverage: CoverageResult,
    issues: Sequence[Issue],
    *,
    mode: str,
    full_audit: bool,
    matrix: CoverageMatrix | None = None,
) -> list[ThemeEntry]:
    """Build ThemeEntry rows for Core (+ Extended when full-audit).

    Sentinel: Core ``sec.*`` only. Review/architecture: all Core; Extended only
    when ``full_audit`` is true.
    """
    matrix = matrix or load_coverage_matrix()
    entries = _entry_map(matrix)
    mode_l = mode.lower()
    rows: list[ThemeEntry] = []

    def add_ids(ids: Iterable[str], pack: str) -> None:
        for cov_id in ids:
            entry = entries.get(cov_id)
            if entry is None or entry.pack != pack:
                continue
            if mode_l == "sentinel" and not cov_id.startswith("sec."):
                continue
            status, notes = _status_for(cov_id, coverage)
            pack_lit: Literal["core", "extended"] = (
                "core" if pack == "core" else "extended"
            )
            status_lit: Literal["covered", "na", "missed"]
            if status == "covered":
                status_lit = "covered"
            elif status == "na":
                status_lit = "na"
            else:
                status_lit = "missed"
            rows.append(
                ThemeEntry(
                    id=cov_id,
                    pack=pack_lit,
                    title=entry.title,
                    status=status_lit,
                    findingCount=_count_findings(cov_id, issues),
                    notes=notes,
                )
            )

    core_order = [e.id for e in matrix.entries if e.pack == "core"]
    ext_order = [e.id for e in matrix.entries if e.pack == "extended"]

    add_ids(core_order, "core")
    if full_audit and mode_l != "sentinel":
        add_ids(ext_order, "extended")

    return rows
