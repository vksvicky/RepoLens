# tests/test_sarif_import.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from repolens.config import ModelConfig, RepoLensConfig, ScannersConfig
from repolens.pipeline import run_review
from repolens.sarif_import import (
    SarifImportResult,
    load_sarif_issues,
    scanner_runs_from_imports,
)
from repolens.schema import Issue, ScannerRun, Severity

FIXTURES = Path(__file__).parent / "fixtures" / "sarif"


def test_import_eslint_relative_path(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.js").write_text("x\ny\neval(user)\n", encoding="utf-8")
    results = load_sarif_issues(FIXTURES / "minimal_eslint.sarif.json", root=tmp_path)
    assert len(results) == 1
    result = results[0]
    assert result.tool_name == "ESLint"
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.file == "src/app.js"
    assert issue.line == 3
    assert issue.source == "scanner"
    assert issue.severity == Severity.HIGH
    assert "sarif" in (issue.category or "").lower() or any(
        "sarif" in s.lower() for s in issue.evidenceSources
    )
    assert issue.impact.strip()
    assert issue.codeExample.strip()


def test_import_skips_path_outside_root(tmp_path: Path) -> None:
    payload = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "X"}},
                "results": [
                    {
                        "ruleId": "r",
                        "level": "error",
                        "message": {"text": "x"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "../escape.py"},
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "bad.sarif.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    results = load_sarif_issues(path, root=tmp_path)
    assert results[0].issues == []
    assert results[0].skipped >= 1


def test_import_tolerates_missing_snippet(tmp_path: Path) -> None:
    (tmp_path / "A.java").write_text("class A {}\n", encoding="utf-8")
    results = load_sarif_issues(FIXTURES / "minimal_sonar.sarif.json", root=tmp_path)
    assert len(results[0].issues) >= 1
    assert results[0].issues[0].line >= 1


def test_rule_id_falls_back_to_nested_rule_id(tmp_path: Path) -> None:
    """CodeQL/Sonar sometimes omit result.ruleId and nest under result.rule.id."""
    (tmp_path / "x.py").write_text("pass\n", encoding="utf-8")
    payload = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "CodeQL"}},
                "results": [
                    {
                        "rule": {"id": "py/sql-injection"},
                        "level": "error",
                        "message": {"text": "SQL injection"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "x.py"},
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "nested.sarif.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    issue = load_sarif_issues(path, root=tmp_path)[0].issues[0]
    assert "py/sql-injection" in issue.title


def test_srcroot_uri_prefix_normalises(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x=1\n", encoding="utf-8")
    payload = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "CodeQL"}},
                "results": [
                    {
                        "ruleId": "r",
                        "level": "warning",
                        "message": {"text": "m"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": "%SRCROOT%/src/a.py",
                                        "uriBaseId": "%SRCROOT%",
                                    },
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "srcroot.sarif.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    issue = load_sarif_issues(path, root=tmp_path)[0].issues[0]
    assert issue.file == "src/a.py"


def test_import_codeql_absolute_file_uri(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "leak.py").write_text("print('secret')\n", encoding="utf-8")
    raw = (FIXTURES / "minimal_codeql.sarif.json").read_text(encoding="utf-8")
    root_uri = tmp_path.resolve().as_uri()
    sarif_path = tmp_path / "codeql.sarif.json"
    sarif_path.write_text(raw.replace("file:///ABS/ROOT", root_uri), encoding="utf-8")
    results = load_sarif_issues(sarif_path, root=tmp_path)
    assert results[0].tool_name == "CodeQL"
    assert len(results[0].issues) == 1
    issue = results[0].issues[0]
    assert issue.file == "src/leak.py"
    assert issue.line == 12
    assert "py/clear-text-logging" in issue.title


def test_multi_run_keeps_per_tool_names(tmp_path: Path) -> None:
    (tmp_path / "a.js").write_text("1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("1\n", encoding="utf-8")
    payload = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "ESLint"}},
                "results": [
                    {
                        "ruleId": "e1",
                        "level": "warning",
                        "message": {"text": "e"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "a.js"},
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            },
            {
                "tool": {"driver": {"name": "CodeQL"}},
                "results": [
                    {
                        "ruleId": "c1",
                        "level": "warning",
                        "message": {"text": "c"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "b.py"},
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            },
        ],
    }
    path = tmp_path / "multi.sarif.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    results = load_sarif_issues(path, root=tmp_path)
    assert [r.tool_name for r in results] == ["ESLint", "CodeQL"]
    assert results[0].issues[0].title.startswith("ESLint:")
    assert results[1].issues[0].title.startswith("CodeQL:")


def test_scanner_runs_from_imports_success() -> None:
    issue = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sarif.ESLint",
        file="a.js",
        line=1,
        title="ESLint: e1",
        explanation="e",
        impact="x",
        recommendedFix="fix",
        codeExample="# x",
        fixTiming="before launch",
        source="scanner",
    )
    runs = scanner_runs_from_imports(
        [SarifImportResult(tool_name="ESLint", issues=[issue], skipped=0)]
    )
    assert len(runs) == 1
    assert runs[0].tool == "sarif:ESLint"
    assert runs[0].status == "ran"
    assert runs[0].findingCount == 1


def test_scanner_runs_from_imports_failed_parse() -> None:
    runs = scanner_runs_from_imports(
        [SarifImportResult(tool_name="sarif", issues=[], skipped=0, detail="no runs")]
    )
    assert runs[0].status == "failed"
    assert runs[0].detail == "no runs"


def test_scanner_runs_from_imports_skipped_only() -> None:
    runs = scanner_runs_from_imports(
        [SarifImportResult(tool_name="X", issues=[], skipped=2)]
    )
    assert runs[0].status == "ran"
    assert runs[0].detail == "skipped 2"


def test_run_review_merges_import_sarif(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.js").write_text("x\ny\neval(user)\n", encoding="utf-8")
    sarif_path = FIXTURES / "minimal_eslint.sarif.json"
    cfg = RepoLensConfig(
        model=ModelConfig(provider=None),
        scanners=ScannersConfig(enabled=[]),
    )
    with patch(
        "repolens.pipeline.run.run_scanners",
        return_value=([], [], []),
    ):
        result = run_review(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            out_dir=tmp_path / "r",
            scanners_only=True,
            scanners="off",
            import_sarif=[sarif_path],
        )
    tools = [r.tool for r in result.report.scannerRuns]
    assert "sarif:ESLint" in tools
    assert any(i.title.startswith("ESLint:") for i in result.report.issues)


def test_fallback_scanner_refresh_keeps_import_sarif_once(tmp_path: Path) -> None:
    """Fallback re-runs scanners and re-imports SARIF; issues must not drop or duplicate."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.js").write_text("x\ny\neval(user)\n", encoding="utf-8")
    sarif_path = FIXTURES / "minimal_eslint.sarif.json"
    cfg = RepoLensConfig(
        model=ModelConfig(provider=None, fallback=True),
        scanners=ScannersConfig(enabled=["semgrep"]),
    )
    mock_run = ScannerRun(tool="semgrep", status="ran", findingCount=0)

    def fake_run_scanners(root: Path, tools: list[str]):
        return ([mock_run], [], [])

    with (
        patch("repolens.llm.setup.detect_ollama", return_value=False),
        patch(
            "repolens.pipeline.run.run_scanners",
            side_effect=fake_run_scanners,
        ) as run_scanners_mock,
    ):
        result = run_review(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            out_dir=tmp_path / "r",
            scanners="off",
            import_sarif=[sarif_path],
        )

    assert run_scanners_mock.call_count >= 1
    eslint_issues = [i for i in result.report.issues if i.title.startswith("ESLint:")]
    assert len(eslint_issues) == 1
    assert "sarif:ESLint" in [r.tool for r in result.report.scannerRuns]
    assert not any("no scanners selected" in g.lower() for g in result.report.durabilityGaps)
