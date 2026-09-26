# tests/test_sarif_import.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from repolens.sarif_import import load_sarif_issues
from repolens.schema import Severity


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
