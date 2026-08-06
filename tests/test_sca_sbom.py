"""Phase 6.2: SCA dedupe, SBOM helpers, license summary, prompt guardrails."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from repolens.scanners.evidence import format_scanner_evidence_for_prompt
from repolens.scanners.sca import (
    build_supply_chain,
    collect_license_ids,
    dedupe_sca_issues,
    parse_cyclonedx_license_summary,
    write_trivy_sbom,
)
from repolens.schema import Issue, Severity


def _issue(
    *,
    category: str,
    title: str,
    file: str = "requirements.txt",
    severity: Severity = Severity.HIGH,
) -> Issue:
    return Issue(
        severity=severity,
        priority="P1",
        category=category,
        file=file,
        line=1,
        title=title,
        explanation="x",
        impact="Known vulnerable dependency may be exploitable in production.",
        recommendedFix="Upgrade",
        codeExample="# upgrade",
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
