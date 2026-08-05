"""Scanner adapters and runner (subprocess mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repolens.config import ModelConfig, RepoLensConfig, ScannersConfig
from repolens.pipeline import ScannerRequirementError, run_review
from repolens.scanners.base import resolve_binary, tools_cache_dir
from repolens.scanners.gitleaks import run_gitleaks
from repolens.scanners.osv import run_osv
from repolens.scanners.runner import missing_required, parse_scanners_flag, run_scanners
from repolens.scanners.semgrep import run_semgrep
from repolens.schema import ScannerRun


def test_parse_scanners_flag_auto_and_off() -> None:
    assert parse_scanners_flag("auto", config_enabled=["gitleaks"]) == ["gitleaks"]
    assert parse_scanners_flag(None, config_enabled=["osv"]) == ["osv"]
    assert parse_scanners_flag("off", config_enabled=["gitleaks"]) is None


def test_parse_scanners_flag_list_and_unknown() -> None:
    assert parse_scanners_flag("gitleaks, osv", config_enabled=[]) == ["gitleaks", "osv"]
    with pytest.raises(ValueError, match="Unknown"):
        parse_scanners_flag("gitleaks,trivy", config_enabled=[])


def test_missing_required() -> None:
    runs = [
        ScannerRun(tool="gitleaks", status="skipped"),
        ScannerRun(tool="osv", status="ran", findingCount=0),
    ]
    assert missing_required(["gitleaks", "osv"], runs) == ["gitleaks"]


def test_resolve_binary_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    tool_dir = tools_cache_dir() / "gitleaks"
    tool_dir.mkdir(parents=True)
    binary = tool_dir / "gitleaks"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    with patch("repolens.scanners.base.shutil.which", return_value=None):
        found = resolve_binary("gitleaks")
    assert found == binary


def test_run_gitleaks_skipped_when_missing() -> None:
    with patch("repolens.scanners.gitleaks.resolve_binary", return_value=None):
        result = run_gitleaks(Path("."))
    assert result.run.status == "skipped"
    assert result.issues == []


def test_run_gitleaks_parses_findings(tmp_path: Path) -> None:
    payload = [
        {
            "File": "app.py",
            "StartLine": 4,
            "RuleID": "aws-access-key",
            "Description": "AWS Access Key",
        }
    ]
    completed = MagicMock(returncode=1, stdout=json.dumps(payload), stderr="")
    with (
        patch("repolens.scanners.gitleaks.resolve_binary", return_value=Path("/bin/gitleaks")),
        patch("repolens.scanners.gitleaks.subprocess.run", return_value=completed),
    ):
        result = run_gitleaks(tmp_path)
    assert result.run.status == "ran"
    assert result.run.findingCount == 1
    assert result.issues[0].severity.value == "HIGH"
    assert result.issues[0].file == "app.py"


def test_semgrep_config_env_override(monkeypatch) -> None:
    from repolens.scanners.semgrep import semgrep_config

    monkeypatch.delenv("REPOLENS_SEMGREP_CONFIG", raising=False)
    assert semgrep_config() == "auto"
    monkeypatch.setenv("REPOLENS_SEMGREP_CONFIG", "./rules.yml")
    assert semgrep_config() == "./rules.yml"


def test_run_semgrep_parses_findings(tmp_path: Path) -> None:
    payload = {
        "results": [
            {
                "check_id": "python.lang.security.audit.eval-detected",
                "path": "x.py",
                "start": {"line": 2},
                "extra": {"severity": "ERROR", "message": "Avoid eval"},
            }
        ]
    }
    completed = MagicMock(returncode=1, stdout=json.dumps(payload), stderr="")
    with (
        patch("repolens.scanners.semgrep.resolve_binary", return_value=Path("/bin/semgrep")),
        patch("repolens.scanners.semgrep.subprocess.run", return_value=completed),
    ):
        result = run_semgrep(tmp_path)
    assert result.run.status == "ran"
    assert len(result.issues) == 1
    assert result.issues[0].codeExample


def test_run_osv_parses_findings(tmp_path: Path) -> None:
    payload = {
        "results": [
            {
                "source": {"path": "requirements.txt"},
                "packages": [
                    {
                        "package": {"name": "requests"},
                        "vulnerabilities": [
                            {"id": "GHSA-xxxx", "summary": "Example vuln"},
                        ],
                    }
                ],
            }
        ]
    }
    completed = MagicMock(returncode=1, stdout=json.dumps(payload), stderr="")
    with (
        patch("repolens.scanners.osv.resolve_binary", return_value=Path("/bin/osv-scanner")),
        patch("repolens.scanners.osv.subprocess.run", return_value=completed),
    ):
        result = run_osv(tmp_path)
    assert result.run.status == "ran"
    assert result.issues[0].title.startswith("GHSA-xxxx")


def test_run_scanners_collects_gaps(tmp_path: Path) -> None:
    runners = {"gitleaks": MagicMock(), "semgrep": MagicMock()}
    with patch("repolens.scanners.runner._RUNNERS", runners) as mocked:
        from repolens.scanners.base import ScannerResult

        gl = mocked["gitleaks"]
        sg = mocked["semgrep"]
        gl.return_value = ScannerResult(
            run=ScannerRun(tool="gitleaks", status="skipped", detail="missing")
        )
        sg.return_value = ScannerResult(
            run=ScannerRun(tool="semgrep", status="ran", findingCount=0)
        )
        runs, issues, gaps = run_scanners(tmp_path, ["gitleaks", "semgrep"])
    assert len(runs) == 2
    assert issues == []
    assert any("gitleaks" in g for g in gaps)


def test_scanners_only_pipeline(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider=None),
        scanners=ScannersConfig(enabled=["gitleaks"]),
    )
    fake_issue_run = ScannerRun(tool="gitleaks", status="ran", findingCount=0)
    with patch(
        "repolens.pipeline.run.run_scanners",
        return_value=([fake_issue_run], [], []),
    ):
        result = run_review(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            out_dir=tmp_path / "r",
            scanners_only=True,
            scanners="auto",
        )
    assert result.dry_run is False
    assert result.report.scannerRuns[0].tool == "gitleaks"
    text = result.markdown_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert "## Automated scanners" in text
    assert "gitleaks" in text


def test_require_scanners_raises(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider=None),
        scanners=ScannersConfig(enabled=["gitleaks"], require=True),
    )
    with (
        patch(
            "repolens.pipeline.run.run_scanners",
            return_value=(
                [ScannerRun(tool="gitleaks", status="skipped", detail="missing")],
                [],
                ["scanner:gitleaks missing"],
            ),
        ),
        pytest.raises(ScannerRequirementError),
    ):
        run_review(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            out_dir=tmp_path / "r",
            scanners_only=True,
            require_scanners=True,
        )
