"""M&A / data-room evidence pack: zip Markdown + SARIF + JSON + SBOM + provenance."""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from repolens.schema import FindingReport

# Canonical zip member order (optional members omitted when absent).
EVIDENCE_MEMBERS: tuple[str, ...] = (
    "audit.md",
    "audit.pdf",
    "findings.json",
    "findings.sarif.json",
    "sbom.cdx.json",
    "provenance.json",
    "NOTES.txt",
)


@dataclass(frozen=True)
class EvidenceInputs:
    markdown: Path
    json_report: Path
    sarif: Path | None
    sbom: Path | None
    report: FindingReport


def resolve_evidence_inputs(report_path: Path) -> EvidenceInputs:
    """Resolve sibling artifacts next to a Markdown or JSON gate report."""
    path = report_path.resolve()
    if path.is_dir():
        jsons = sorted(
            p
            for p in path.glob("gate_review_report_*.json")
            if not p.name.endswith(".sarif.json")
        )
        if not jsons:
            raise FileNotFoundError(f"No gate_review_report_*.json under {path}")
        path = jsons[-1]

    if path.suffix == ".json" and not path.name.endswith(".sarif.json"):
        json_path = path
        md_path = path.with_suffix(".md")
    elif path.suffix == ".md":
        md_path = path
        json_path = path.with_suffix(".json")
    else:
        raise FileNotFoundError(
            f"Expected a gate report .md or .json path, got {path.name}"
        )

    if not json_path.is_file():
        raise FileNotFoundError(f"Missing findings json next to report: {json_path}")
    if not md_path.is_file():
        raise FileNotFoundError(f"Missing markdown report: {md_path}")

    report = FindingReport.model_validate_json(json_path.read_text(encoding="utf-8"))
    sarif = path.parent / f"{path.stem}.sarif.json"
    if path.suffix == ".md":
        sarif = path.with_suffix(".sarif.json")
    elif path.suffix == ".json":
        # stem is gate_…_HHMM → gate_…_HHMM.sarif.json
        sarif = path.parent / f"{path.stem}.sarif.json"
    if not sarif.is_file():
        sarif = None

    sbom: Path | None = None
    sc = report.supplyChain
    if sc and sc.sbomPath:
        candidate = Path(sc.sbomPath)
        if not candidate.is_file():
            candidate = path.parent / candidate.name
        if candidate.is_file():
            sbom = candidate
    if sbom is None:
        fallback = path.parent / "sbom.cdx.json"
        if fallback.is_file():
            sbom = fallback

    return EvidenceInputs(
        markdown=md_path,
        json_report=json_path,
        sarif=sarif,
        sbom=sbom,
        report=report,
    )


def _utc_stamp(when_stamp: str | None) -> str:
    if when_stamp:
        return when_stamp
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _try_pandoc_pdf(markdown: Path, work: Path) -> Path | None:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return None
    pdf = work / "audit.pdf"
    completed = subprocess.run(
        [pandoc, str(markdown), "-o", str(pdf)],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0 or not pdf.is_file():
        return None
    return pdf


def _provenance_payload(
    report: FindingReport, *, pandoc_pdf: bool, notes: list[str]
) -> dict:
    prov = report.provenance
    body: dict = {
        "repoLensVersion": prov.repoLensVersion if prov else None,
        "gitSha": prov.gitSha if prov else None,
        "dirtyTree": prov.dirtyTree if prov else None,
        "provider": prov.provider if prov else None,
        "model": prov.model if prov else None,
        "scannerTools": list(prov.scannerTools) if prov else [],
        "scannerDigests": dict(prov.scannerDigests) if prov else {},
        "promptTemplateHash": prov.promptTemplateHash if prov else None,
        "journalTipHash": prov.journalTipHash if prov else None,
        "pandocPdf": pandoc_pdf,
        "notes": notes,
    }
    return body


def build_evidence_pack(
    report_path: Path,
    out_dir: Path,
    *,
    when_stamp: str | None = None,
    try_pdf: bool = True,
) -> Path:
    """Write a timestamped evidence zip; return its path."""
    inputs = resolve_evidence_inputs(report_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp(when_stamp)
    zip_path = out_dir / f"repolens-evidence-{stamp}.zip"
    work = out_dir / f".evidence-work-{stamp}"
    work.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    try:
        members: dict[str, Path | bytes] = {
            "audit.md": inputs.markdown,
            "findings.json": inputs.json_report,
        }
        if inputs.sarif is not None:
            members["findings.sarif.json"] = inputs.sarif
        else:
            notes.append("SARIF skipped: no sibling *.sarif.json found.")
        if inputs.sbom is not None:
            members["sbom.cdx.json"] = inputs.sbom
        else:
            notes.append("SBOM skipped: no CycloneDX artifact available.")

        pdf_path: Path | None = None
        if try_pdf:
            pdf_path = _try_pandoc_pdf(inputs.markdown, work)
        if pdf_path is not None:
            members["audit.pdf"] = pdf_path
        else:
            notes.append(
                "PDF skipped: pandoc missing or conversion failed "
                "(Markdown remains the archival report)."
            )

        prov_bytes = json.dumps(
            _provenance_payload(
                inputs.report, pandoc_pdf=pdf_path is not None, notes=list(notes)
            ),
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        members["provenance.json"] = prov_bytes
        if notes:
            members["NOTES.txt"] = ("\n".join(notes) + "\n").encode("utf-8")

        ordered = [name for name in EVIDENCE_MEMBERS if name in members]
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in ordered:
                payload = members[name]
                info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                if isinstance(payload, bytes):
                    zf.writestr(info, payload)
                else:
                    zf.writestr(info, payload.read_bytes())
        return zip_path
    finally:
        shutil.rmtree(work, ignore_errors=True)
