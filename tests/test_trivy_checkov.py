"""Phase 6.1: Trivy / Checkov JSON parsers and runner wiring."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from repolens.plugins import KNOWN_PLUGINS, catalog
from repolens.scanners.checkov import parse_checkov_report, run_checkov
from repolens.scanners.runner import _RUNNERS, parse_scanners_flag
from repolens.scanners.trivy import parse_trivy_report, run_trivy
from repolens.schema import Severity


def test_parse_trivy_vulnerabilities_and_misconfigs() -> None:
    payload = {
        "Results": [
            {
                "Target": "requirements.txt",
                "Class": "lang-pkgs",
                "Type": "pip",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2024-0001",
                        "PkgName": "demo",
                        "InstalledVersion": "1.0.0",
                        "FixedVersion": "1.0.1",
                        "Severity": "HIGH",
                        "Title": "Demo vuln",
                        "Description": "Bad package",
                    }
                ],
            },
            {
                "Target": "Dockerfile",
                "Class": "config",
                "Type": "dockerfile",
                "Misconfigurations": [
                    {
                        "ID": "DS002",
                        "Title": "Image user should not be root",
                        "Description": "Running as root",
                        "Severity": "MEDIUM",
                        "PrimaryURL": "https://example.com/ds002",
                        "CauseMetadata": {"StartLine": 12, "EndLine": 12},
                    }
                ],
            },
        ]
    }
    issues = parse_trivy_report(payload)
    assert len(issues) == 2
    vuln = next(i for i in issues if "CVE-2024-0001" in i.title)
    assert vuln.severity == Severity.HIGH
    assert vuln.category == "trivy"
    assert vuln.file == "requirements.txt"
    assert "demo" in vuln.recommendedFix
    mis = next(i for i in issues if "DS002" in i.title)
    assert mis.severity == Severity.MEDIUM
    assert mis.file == "Dockerfile"
    assert mis.line == 12


def test_parse_checkov_failed_checks() -> None:
    payload = {
        "results": {
            "failed_checks": [
                {
                    "check_id": "CKV_AWS_20",
                    "check_name": "S3 Bucket has an ACL defined which allows public READ access",
                    "file_path": "/tmp/repo/infra/s3.tf",
                    "repo_file_path": "/infra/s3.tf",
                    "file_line_range": [4, 10],
                    "severity": "HIGH",
                    "guideline": "https://docs.bridgecrew.io/docs/s3_20-public-access",
                }
            ]
        }
    }
    issues = parse_checkov_report(payload, root=Path("/tmp/repo"))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == Severity.HIGH
    assert issue.category == "checkov"
    assert issue.file == "infra/s3.tf"
    assert issue.line == 4
    assert "CKV_AWS_20" in issue.title


def test_run_trivy_skipped_when_missing() -> None:
    with patch("repolens.scanners.trivy.resolve_binary", return_value=None):
        result = run_trivy(Path("."))
    assert result.run.status == "skipped"
    assert result.issues == []


def test_run_checkov_skipped_when_missing() -> None:
    with patch("repolens.scanners.checkov.resolve_binary", return_value=None):
        result = run_checkov(Path("."))
    assert result.run.status == "skipped"


def test_catalog_and_runners_include_trivy_checkov() -> None:
    cat = catalog()
    assert "trivy" in cat
    assert "checkov" in cat
    assert set(KNOWN_PLUGINS) >= {"gitleaks", "semgrep", "osv", "trivy", "checkov"}
    for plat, spec in cat["trivy"].items():
        assert spec.sha256 and len(spec.sha256) == 64, plat
    assert all(s.kind == "pip" for s in cat["checkov"].values())
    assert "trivy" in _RUNNERS
    assert "checkov" in _RUNNERS


def test_parse_scanners_flag_accepts_trivy_checkov() -> None:
    tools = parse_scanners_flag(
        "trivy,checkov",
        config_enabled=["gitleaks", "semgrep", "osv"],
    )
    assert tools == ["trivy", "checkov"]


def test_format_scanner_evidence_for_prompt() -> None:
    from repolens.scanners.evidence import format_scanner_evidence_for_prompt
    from repolens.schema import Issue

    text = format_scanner_evidence_for_prompt(
        [
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="trivy",
                file="Dockerfile",
                line=1,
                title="DS002 Image user",
                explanation="root",
                impact="privilege",
                recommendedFix="USER nonroot",
                codeExample="USER app",
            )
        ]
    )
    assert "Scanner evidence" in text
    assert "DS002" in text
    assert "Dockerfile" in text
