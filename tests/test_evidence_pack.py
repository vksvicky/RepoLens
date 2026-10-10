"""M&A evidence pack zip (#105)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repolens.cli import app
from repolens.evidence_pack import (
    EVIDENCE_MEMBERS,
    build_evidence_pack,
    resolve_evidence_inputs,
)
from repolens.schema import FindingReport, ProvenanceBlock, Summary, SupplyChainBlock

runner = CliRunner()


def _write_report_bundle(tmp_path: Path, *, with_sbom: bool = True) -> Path:
    """Create a minimal reports dir with md/json/sarif (+ optional sbom)."""
    out = tmp_path / "reports"
    out.mkdir()
    stem = "gate_review_report_review_2026-10-09_1200"
    (out / f"{stem}.md").write_text("# Gate review\n\nsample\n", encoding="utf-8")
    report = FindingReport(
        confidence=88,
        summary=Summary(high=1),
        provenance=ProvenanceBlock(
            repoLensVersion="0.1.1",
            gitSha="abc123",
            model="gpt-4.1-mini",
            provider="openai",
            scannerTools=["gitleaks", "semgrep"],
            scannerDigests={"gitleaks": "deadbeef"},
            promptTemplateHash="tmplhash",
            journalTipHash="tiphash",
            dirtyTree=False,
        ),
        supplyChain=SupplyChainBlock(
            sbomPath=str(out / "sbom.cdx.json") if with_sbom else None,
            sbomFormat="cyclonedx" if with_sbom else None,
        ),
    )
    (out / f"{stem}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out / f"{stem}.sarif.json").write_text(
        json.dumps({"version": "2.1.0", "runs": []}), encoding="utf-8"
    )
    if with_sbom:
        (out / "sbom.cdx.json").write_text(
            json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.5"}),
            encoding="utf-8",
        )
    return out / f"{stem}.md"


def test_resolve_inputs_from_markdown_sibling_artifacts(tmp_path: Path) -> None:
    md = _write_report_bundle(tmp_path)
    inputs = resolve_evidence_inputs(md)
    assert inputs.markdown == md
    assert inputs.json_report.name.endswith(".json")
    assert inputs.sarif is not None and inputs.sarif.name.endswith(".sarif.json")
    assert inputs.sbom is not None and inputs.sbom.name == "sbom.cdx.json"


def test_build_evidence_pack_zip_membership_and_order(tmp_path: Path) -> None:
    md = _write_report_bundle(tmp_path)
    dest = tmp_path / "packs"
    zip_path = build_evidence_pack(md, dest, when_stamp="20261009T120000Z")
    assert zip_path.name.startswith("repolens-evidence-")
    assert zip_path.suffix == ".zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    # Deterministic order; PDF may be absent → NOTES.txt instead
    assert names[0] == "audit.md"
    assert "findings.json" in names
    assert "findings.sarif.json" in names
    assert "sbom.cdx.json" in names
    assert "provenance.json" in names
    assert names.index("findings.json") < names.index("findings.sarif.json")
    assert names.index("findings.sarif.json") < names.index("sbom.cdx.json")
    assert names.index("sbom.cdx.json") < names.index("provenance.json")
    # No unexpected members beyond known set
    allowed = set(EVIDENCE_MEMBERS) | {"NOTES.txt", "audit.pdf"}
    assert set(names) <= allowed


def test_build_evidence_pack_provenance_contents(tmp_path: Path) -> None:
    md = _write_report_bundle(tmp_path)
    zip_path = build_evidence_pack(md, tmp_path / "out", when_stamp="20261009T120000Z")
    with zipfile.ZipFile(zip_path) as zf:
        prov = json.loads(zf.read("provenance.json"))
    assert prov["gitSha"] == "abc123"
    assert prov["provider"] == "openai"
    assert prov["model"] == "gpt-4.1-mini"
    assert prov["scannerDigests"]["gitleaks"] == "deadbeef"
    assert prov["promptTemplateHash"] == "tmplhash"
    assert prov["journalTipHash"] == "tiphash"
    assert "pandocPdf" in prov  # bool: whether PDF was included


def test_build_evidence_pack_without_sbom_omits_member(tmp_path: Path) -> None:
    md = _write_report_bundle(tmp_path, with_sbom=False)
    zip_path = build_evidence_pack(md, tmp_path / "out", when_stamp="t")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "sbom.cdx.json" not in names
    assert "NOTES.txt" in names  # records skipped optional artifacts


def test_cli_export_evidence_pack(tmp_path: Path) -> None:
    md = _write_report_bundle(tmp_path)
    result = runner.invoke(
        app,
        ["export", str(md), "--evidence-pack", "--out", str(tmp_path / "packs")],
    )
    assert result.exit_code == 0, result.output
    zips = list((tmp_path / "packs").glob("repolens-evidence-*.zip"))
    assert len(zips) == 1


def test_resolve_rejects_missing_json(tmp_path: Path) -> None:
    md = tmp_path / "alone.md"
    md.write_text("# x\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="json"):
        resolve_evidence_inputs(md)
