"""Phase 5.2 — Core + Extended theme registry and report breakdown."""

from __future__ import annotations

from pathlib import Path

from repolens.coverage import coverage_ids_for_pass, evaluate_coverage, load_coverage_matrix
from repolens.report import write_markdown_report
from repolens.schema import (
    CoverageBlock,
    FindingReport,
    Issue,
    Severity,
    Summary,
    ThemeEntry,
)
from repolens.themes import (
    CORE_THEME_IDS,
    EXTENDED_THEME_IDS,
    HEURISTIC_TO_THEME,
    build_theme_breakdown,
    canonicalize_coverage_id,
    theme_id_for_category,
)


def test_coverage_matrix_has_core_and_extended_packs() -> None:
    matrix = load_coverage_matrix()
    by_id = {e.id: e for e in matrix.entries}
    for cid in CORE_THEME_IDS:
        assert cid in by_id, f"missing Core theme {cid}"
        assert by_id[cid].pack == "core"
    for cid in EXTENDED_THEME_IDS:
        assert cid in by_id, f"missing Extended theme {cid}"
        assert by_id[cid].pack == "extended"
    # Deprecated coarse ids must not remain as scored theme rows
    for deprecated in (
        "arch.structure",
        "arch.code_quality",
        "arch.security_surface",
        "sec.secrets",
        "sec.deps_config",
        "sec.practice_review",
    ):
        assert deprecated not in by_id


def test_canonicalize_and_heuristic_theme_map() -> None:
    assert canonicalize_coverage_id("sec.secrets") == "sec.repo_hygiene_secrets"
    assert canonicalize_coverage_id("sec.deps_config") == "sec.deps_supply_chain"
    assert theme_id_for_category("heuristic.mega_file") == "arch.structure_size"
    assert theme_id_for_category("heuristic.sibling_duplication") == "arch.duplication"
    assert theme_id_for_category("heuristic.gitignore_secrets") == (
        "sec.repo_hygiene_secrets"
    )
    assert theme_id_for_category("heuristic.ci_gaps") == "arch.ci_durability"
    assert set(HEURISTIC_TO_THEME.values()) <= (CORE_THEME_IDS | EXTENDED_THEME_IDS)


def test_evaluate_coverage_aliases_and_heuristic_categories() -> None:
    issues = [
        Issue(
            severity=Severity.MEDIUM,
            priority="P2",
            category="heuristic.gitignore_secrets",
            file=".gitignore",
            line=1,
            title="Secrets hygiene gap",
            explanation="env files not ignored",
            impact="",
            recommendedFix="ignore .env",
            codeExample="",
        )
    ]
    result = evaluate_coverage(
        ["sec.repo_hygiene_secrets", "sec.injection"],
        issues,
        [],
    )
    # Heuristic category maps → covered for repo hygiene
    assert "sec.repo_hygiene_secrets" in result.covered
    # Alias N/A on old id should apply to canonical id when present in wanted
    result2 = evaluate_coverage(
        ["sec.repo_hygiene_secrets"],
        [],
        ["coverage:sec.secrets: N/A — no secret material in pack"],
    )
    assert "sec.repo_hygiene_secrets" in result2.na


def test_build_theme_breakdown_core_only_without_full_audit() -> None:
    issues = [
        Issue(
            severity=Severity.MEDIUM,
            priority="P2",
            category="heuristic.mega_file",
            file="Big.swift",
            line=1,
            title="Mega-file",
            explanation="too big",
            impact="",
            recommendedFix="split",
            codeExample="",
        )
    ]
    coverage = evaluate_coverage(
        list(CORE_THEME_IDS) + list(EXTENDED_THEME_IDS),
        issues,
        ["coverage:arch.database: N/A — no persistence layer"],
    )
    themes = build_theme_breakdown(
        coverage,
        issues,
        mode="review",
        full_audit=False,
    )
    packs = {t.pack for t in themes}
    assert packs == {"core"}
    mega = next(t for t in themes if t.id == "arch.structure_size")
    assert mega.status == "covered"
    assert mega.findingCount >= 1


def test_build_theme_breakdown_extended_on_full_audit() -> None:
    coverage = evaluate_coverage(
        list(CORE_THEME_IDS) + list(EXTENDED_THEME_IDS),
        [],
        ["coverage:arch.database: N/A — no persistence layer"],
    )
    themes = build_theme_breakdown(
        coverage, [], mode="review", full_audit=True
    )
    assert any(t.pack == "extended" for t in themes)
    db = next(t for t in themes if t.id == "arch.database")
    assert db.status == "na"
    assert "persistence" in (db.notes or "").lower() or db.notes


def test_build_theme_breakdown_sentinel_core_p1_only() -> None:
    coverage = evaluate_coverage(list(CORE_THEME_IDS), [], [])
    themes = build_theme_breakdown(
        coverage, [], mode="sentinel", full_audit=False
    )
    assert themes
    assert all(t.pack == "core" for t in themes)
    assert all(t.id.startswith("sec.") for t in themes)


def test_markdown_theme_breakdown_sections(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=60,
        summary=Summary(),
        issues=[],
        coverage=CoverageBlock(
            covered=["arch.structure_size"],
            na={"arch.database": "no persistence layer"},
            missed=["sec.injection"],
        ),
        themes=[
            ThemeEntry(
                id="arch.structure_size",
                pack="core",
                title="Structure & size",
                status="covered",
                findingCount=0,
            ),
            ThemeEntry(
                id="sec.injection",
                pack="core",
                title="Injection & unsafe code",
                status="missed",
                findingCount=0,
            ),
            ThemeEntry(
                id="arch.database",
                pack="extended",
                title="Database & data integrity",
                status="na",
                findingCount=0,
                notes="no persistence layer",
            ),
        ],
    )
    path = write_markdown_report(report, tmp_path, mode="review")
    text = path.read_text(encoding="utf-8")
    assert "## Theme breakdown" in text
    assert "### Core" in text
    assert "### Extended" in text
    assert "Structure & size" in text
    assert "Database & data integrity" in text


def test_coverage_ids_for_pass_includes_new_core_themes() -> None:
    enabled = {"security", "architecture", "reliability"}
    p1 = coverage_ids_for_pass("p1", full_audit=False, enabled_rule_ids=enabled)
    assert "sec.repo_hygiene_secrets" in p1
    assert "sec.transport_tls" in p1
    assert "sec.data_exposure" in p1
    assert "sec.secrets" not in p1
    p3 = coverage_ids_for_pass("p3", full_audit=False, enabled_rule_ids=enabled)
    assert "arch.structure_size" in p3
    assert "arch.duplication" in p3
    assert "arch.database" not in p3  # full_audit_only
    p3_full = coverage_ids_for_pass("p3", full_audit=True, enabled_rule_ids=enabled)
    assert "arch.database" in p3_full
    assert "arch.observability" in p3_full
