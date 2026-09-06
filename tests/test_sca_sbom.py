"""Phase 6.2: SCA dedupe, SBOM helpers, license summary, prompt guardrails."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from repolens.scanners.evidence import format_scanner_evidence_for_prompt
from repolens.scanners.sca import (
    build_supply_chain,
    collect_license_ids,
    dedupe_cross_source_sca_issues,
    dedupe_sca_issues,
    extract_advisory_id,
    parse_cyclonedx_license_summary,
    write_trivy_sbom,
)
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(
    *,
    category: str,
    title: str,
    file: str = "requirements.txt",
    severity: Severity = Severity.HIGH,
    source: str | None = None,
    package_name: str | None = None,
    advisory: str | None = None,
    explanation: str = "x",
) -> Issue:
    return Issue(
        severity=severity,
        priority="P1",
        category=category,
        file=file,
        line=1,
        title=title,
        explanation=explanation,
        impact="Known vulnerable dependency may be exploitable in production.",
        recommendedFix="Upgrade",
        codeExample="# upgrade",
        source=source,  # type: ignore[arg-type]
        packageName=package_name,
        advisoryId=advisory,
    )


def test_dedupe_sca_keeps_one_issue_per_cve_package() -> None:
    issues = [
        _issue(category="osv", title="CVE-2024-1234 in demo"),
        _issue(category="trivy", title="CVE-2024-1234 in demo: Demo vuln"),
        _issue(category="trivy", title="CVE-2024-9999 in other"),
        _issue(
            category="checkov",
            title="CKV_AWS_20: public bucket",
            file="s3.tf",
            severity=Severity.MEDIUM,
        ),
    ]
    out = dedupe_sca_issues(issues)
    titles = [i.title for i in out]
    assert sum("CVE-2024-1234" in t for t in titles) == 1
    assert any("CVE-2024-9999" in t for t in titles)
    assert any("CKV_AWS_20" in t for t in titles)
    # Prefer osv when both present
    kept = next(i for i in out if "CVE-2024-1234" in i.title)
    assert kept.category == "osv"


def test_parse_cyclonedx_license_summary() -> None:
    bom = {
        "components": [
            {
                "name": "left-pad",
                "version": "1.0.0",
                "licenses": [{"license": {"id": "MIT"}}],
            },
            {
                "name": "copyleft-demo",
                "version": "2.0.0",
                "licenses": [{"license": {"name": "GPL-3.0-only"}}],
            },
            {
                "name": "unknown-pkg",
                "version": "0.1.0",
                "licenses": [],
            },
        ]
    }
    notes = parse_cyclonedx_license_summary(bom)
    assert any("left-pad" in n and "MIT" in n for n in notes)
    assert any("GPL-3.0" in n for n in notes)
    assert any("copyleft" in n.lower() or "GPL" in n for n in notes)


def test_write_trivy_sbom_skipped_without_binary(tmp_path: Path) -> None:
    with patch("repolens.scanners.sca.resolve_binary", return_value=None):
        path, detail = write_trivy_sbom(tmp_path, tmp_path / "out")
    assert path is None
    assert "not found" in detail


def test_write_trivy_sbom_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "reports"
    fake_bin = tmp_path / "trivy"
    fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        # trivy ... -o <path>
        dest = Path(cmd[cmd.index("-o") + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text('{"bomFormat":"CycloneDX","components":[]}\n', encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    with (
        patch("repolens.scanners.sca.resolve_binary", return_value=fake_bin),
        patch("repolens.scanners.sca.subprocess.run", side_effect=fake_run),
    ):
        path, detail = write_trivy_sbom(tmp_path / "repo", out)
    assert path is not None
    assert path.is_file()
    assert "cyclonedx" in detail.lower() or path.suffix == ".json"


def test_scanner_evidence_forbids_llm_dep_graph_reasoning() -> None:
    text = format_scanner_evidence_for_prompt(
        [
            _issue(category="osv", title="CVE-2024-1 in x"),
        ]
    )
    assert "do not invent" in text.lower() or "must not" in text.lower()
    assert "lockfile" in text.lower() or "dependency graph" in text.lower()
    assert "reachability" in text.lower()


def test_collect_license_ids_sorted_unique() -> None:
    bom = {
        "components": [
            {"name": "a", "licenses": [{"license": {"id": "MIT"}}]},
            {"name": "b", "licenses": [{"license": {"id": "Apache-2.0"}}]},
            {"name": "c", "licenses": [{"license": {"id": "MIT"}}]},
        ]
    }
    assert collect_license_ids(bom) == ["Apache-2.0", "MIT"]


def test_build_supply_chain_writes_block(tmp_path: Path) -> None:
    out = tmp_path / "reports"
    fake_bin = tmp_path / "trivy"
    fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_bin.chmod(0o755)
    bom = {
        "bomFormat": "CycloneDX",
        "components": [
            {
                "name": "left-pad",
                "version": "1.0.0",
                "licenses": [{"license": {"id": "MIT"}}],
            }
        ],
    }

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        dest = Path(cmd[cmd.index("-o") + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(__import__("json").dumps(bom), encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    with (
        patch("repolens.scanners.sca.resolve_binary", return_value=fake_bin),
        patch("repolens.scanners.sca.subprocess.run", side_effect=fake_run),
    ):
        block, gaps = build_supply_chain(tmp_path / "repo", out)
    assert not gaps
    assert block is not None
    assert block.sbomPath == "sbom.cdx.json"
    assert block.sbomFormat == "cyclonedx"
    assert "MIT" in block.licenses
    assert any("left-pad" in n for n in block.notes)


def test_extract_advisory_id_recognises_standard_ids() -> None:
    cases = [
        ("CVE-2024-12345 in paste", "CVE-2024-12345"),
        ("see ghsa-3x3c-cg28-v232", "GHSA-3X3C-CG28-V232"),
        ("RUSTSEC-2020-0071 advisory", "RUSTSEC-2020-0071"),
        ("PYSEC-2021-100 details", "PYSEC-2021-100"),
        ("GO-2022-0965 in module", "GO-2022-0965"),
        ("explanation cites CVE-2023-99999 later", "CVE-2023-99999"),
    ]
    for text, expected in cases:
        assert extract_advisory_id(text) == expected


def test_extract_advisory_id_returns_none_without_pattern() -> None:
    assert extract_advisory_id("generic secret hygiene finding") is None
    assert extract_advisory_id("") is None


def test_issue_evidence_sources_and_report_raw_counts_default() -> None:
    issue = _issue(category="osv", title="CVE-2024-1 in x")
    assert issue.evidenceSources == []
    report = FindingReport(confidence=50, summary=Summary(), issues=[issue])
    assert report.rawCriticalHighCount is None
    assert report.rawTotalFindings is None


def test_cross_source_dedupe_prefers_scanner_severity() -> None:
    scanner = _issue(
        category="osv",
        title="CVE-2024-12345 in paste",
        severity=Severity.HIGH,
        source="scanner",
        package_name="paste",
        advisory="CVE-2024-12345",
    )
    llm = _issue(
        category="sec.supply_chain",
        title="CVE-2024-12345 paste is Critical",
        file="src/main.py",
        severity=Severity.CRITICAL,
        source="llm",
        package_name="paste",
        explanation="CVE-2024-12345 affects paste",
    )
    other = _issue(
        category="heuristic.mega_file",
        title="large file",
        file="big.py",
        severity=Severity.MEDIUM,
        source="heuristic",
    )
    deduped, raw_ch, raw_total = dedupe_cross_source_sca_issues(
        [scanner, llm, other]
    )
    assert raw_total == 3
    assert raw_ch == 2
    assert len(deduped) == 2
    primary = next(i for i in deduped if extract_advisory_id(i.title))
    assert primary.severity == Severity.HIGH
    assert primary.category == "osv"
    assert "osv" in primary.evidenceSources
    assert "llm" in primary.evidenceSources
    assert any(i.category == "heuristic.mega_file" for i in deduped)


def test_cross_source_dedupe_keeps_llm_only_advisory() -> None:
    llm = _issue(
        category="sec.supply_chain",
        title="RUSTSEC-2024-0436 in paste",
        severity=Severity.HIGH,
        source="llm",
        package_name="paste",
    )
    deduped, raw_ch, raw_total = dedupe_cross_source_sca_issues([llm])
    assert raw_total == 1
    assert raw_ch == 1
    assert len(deduped) == 1
    assert deduped[0].severity == Severity.HIGH
    # Same-source / single-row: no collapse — leave evidenceSources unset.
    assert deduped[0].evidenceSources == []


def test_cross_source_dedupe_passthrough_without_advisory() -> None:
    issue = _issue(
        category="sec.injection",
        title="possible injection in handler",
        severity=Severity.HIGH,
        source="llm",
    )
    deduped, raw_ch, raw_total = dedupe_cross_source_sca_issues([issue])
    assert deduped == [issue]
    assert raw_ch == 1
    assert raw_total == 1


def test_cross_source_dedupe_keeps_distinct_ecosystems() -> None:
    """Sourcery: empty ecosystem must not collapse PyPI vs npm same name."""
    pypi = _issue(
        category="osv",
        title="CVE-2024-1111 in lodash",
        file="requirements.txt",
        severity=Severity.HIGH,
        source="scanner",
        package_name="lodash",
        advisory="CVE-2024-1111",
    )
    npm = _issue(
        category="osv",
        title="CVE-2024-1111 in lodash",
        file="package-lock.json",
        severity=Severity.HIGH,
        source="scanner",
        package_name="lodash",
        advisory="CVE-2024-1111",
    )
    deduped, _, _ = dedupe_cross_source_sca_issues([pypi, npm])
    assert len(deduped) == 2


def test_cross_source_dedupe_preserves_same_source_llm_rows() -> None:
    """Sourcery: only collapse scanner↔LLM, not multiple LLM rows."""
    a = _issue(
        category="sec.supply_chain",
        title="CVE-2024-2222 in demo",
        file="a.py",
        severity=Severity.HIGH,
        source="llm",
        package_name="demo",
    )
    b = _issue(
        category="sec.supply_chain",
        title="CVE-2024-2222 in demo (retry)",
        file="b.py",
        severity=Severity.CRITICAL,
        source="llm",
        package_name="demo",
    )
    deduped, raw_ch, raw_total = dedupe_cross_source_sca_issues([a, b])
    assert raw_total == 2
    assert raw_ch == 2
    assert len(deduped) == 2


def test_cross_source_dedupe_rejects_unknown_ecosystem_different_paths() -> None:
    """Sourcery: unknown↔unknown must not merge across distinct lockfile paths."""
    scanner = _issue(
        category="osv",
        title="CVE-2024-3333 in demo",
        file="vendor/custom.lock",
        severity=Severity.HIGH,
        source="scanner",
        package_name="demo",
        advisory="CVE-2024-3333",
    )
    llm = _issue(
        category="sec.supply_chain",
        title="CVE-2024-3333 in demo",
        file="src/app.js",
        severity=Severity.CRITICAL,
        source="llm",
        package_name="demo",
    )
    deduped, _, _ = dedupe_cross_source_sca_issues([scanner, llm])
    assert len(deduped) == 2
    assert all(i.severity != Severity.HIGH or i.source == "scanner" for i in deduped)
    # Both rows retained (no collapse).
    assert {i.file for i in deduped} == {"vendor/custom.lock", "src/app.js"}


def test_cross_source_dedupe_allows_known_unknown_pair() -> None:
    """Known lockfile ecosystem may still merge with an LLM row on source code."""
    scanner = _issue(
        category="osv",
        title="CVE-2024-4444 in demo",
        file="package-lock.json",
        severity=Severity.HIGH,
        source="scanner",
        package_name="demo",
        advisory="CVE-2024-4444",
    )
    llm = _issue(
        category="sec.supply_chain",
        title="CVE-2024-4444 in demo",
        file="src/index.js",
        severity=Severity.CRITICAL,
        source="llm",
        package_name="demo",
    )
    deduped, _, _ = dedupe_cross_source_sca_issues([scanner, llm])
    assert len(deduped) == 1
    assert deduped[0].severity == Severity.HIGH
    assert "llm" in deduped[0].evidenceSources


def test_cross_source_dedupe_preserves_original_order() -> None:
    """Sourcery: do not move advisory rows after all passthrough findings."""
    heur = _issue(
        category="heuristic.mega_file",
        title="large file",
        file="big.py",
        severity=Severity.MEDIUM,
        source="heuristic",
    )
    scanner = _issue(
        category="osv",
        title="RUSTSEC-2024-0436 in paste",
        file="Cargo.lock",
        severity=Severity.HIGH,
        source="scanner",
        package_name="paste",
        advisory="RUSTSEC-2024-0436",
    )
    mid = _issue(
        category="heuristic.deep_nesting",
        title="nesting",
        file="ui.py",
        severity=Severity.LOW,
        source="heuristic",
    )
    llm = _issue(
        category="sec.supply_chain",
        title="RUSTSEC-2024-0436 paste Critical",
        file="src/lib.rs",
        severity=Severity.CRITICAL,
        source="llm",
        package_name="paste",
    )
    deduped, _, _ = dedupe_cross_source_sca_issues([heur, scanner, mid, llm])
    assert len(deduped) == 3
    assert [i.category for i in deduped] == [
        "heuristic.mega_file",
        "osv",
        "heuristic.deep_nesting",
    ]
    assert deduped[1].severity == Severity.HIGH
    assert "llm" in deduped[1].evidenceSources
