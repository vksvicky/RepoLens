"""Phase 6.9: Trivy/OSV populate SCA metadata fields."""

from __future__ import annotations

from repolens.scanners.osv import run_osv
from repolens.scanners.trivy import parse_trivy_report


def test_trivy_parse_sets_package_and_versions() -> None:
    data = {
        "Results": [
            {
                "Target": "poetry.lock",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2024-9999",
                        "PkgName": "requests",
                        "InstalledVersion": "2.28.0",
                        "FixedVersion": "2.32.0",
                        "Severity": "HIGH",
                        "Title": "demo",
                        "Description": "desc",
                    }
                ],
            }
        ]
    }
    issues = parse_trivy_report(data)
    assert len(issues) == 1
    assert issues[0].packageName == "requests"
    assert issues[0].installedVersion == "2.28.0"
    assert issues[0].fixedVersion == "2.32.0"
    assert issues[0].advisoryId == "CVE-2024-9999"


def test_osv_parse_sets_package_and_advisory(tmp_path, monkeypatch) -> None:
    # Unit-test via constructing the same shape as run_osv JSON path
    # by calling internal mapping through a tiny fake: re-use parse by mocking subprocess.
    import json
    import subprocess

    from repolens.scanners import osv as osv_mod

    payload = {
        "results": [
            {
                "source": {"path": "requirements.txt"},
                "packages": [
                    {
                        "package": {"name": "django"},
                        "vulnerabilities": [
                            {"id": "GHSA-xxxx", "summary": "issue"}
                        ],
                    }
                ],
            }
        ]
    }

    class _Done:
        returncode = 0
        stdout = json.dumps(payload)
        stderr = ""

    monkeypatch.setattr(osv_mod, "resolve_binary", lambda *a, **k: "/bin/osv")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _Done(),
    )
    result = run_osv(tmp_path)
    assert result.issues[0].packageName == "django"
    assert result.issues[0].advisoryId == "GHSA-xxxx"
