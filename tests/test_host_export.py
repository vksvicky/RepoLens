"""Shared inclusion rule for host widgets. GitLab and Bitbucket both use it."""

from __future__ import annotations

from repolens.host_export import counts_as_trusted, export_path
from repolens.schema import Issue, Severity


def _issue(**kwargs: object) -> Issue:
    base: dict = {
        "severity": Severity.MEDIUM,
        "priority": "P3",
        "category": "heuristic.large_function",
        "file": "src/process.py",
        "line": 45,
        "title": "Large function",
        "explanation": "Long.",
        "recommendedFix": "Split it.",
        "source": "heuristic",
    }
    base.update(kwargs)
    return Issue(**base)


def test_export_path_drops_unsafe_paths_and_normalizes_slashes() -> None:
    assert export_path("src\\mod.py") == "src/mod.py"
    assert export_path("../etc/passwd") is None
    assert export_path("/etc/passwd") is None
    assert export_path("~/.ssh/id_rsa") is None
    assert export_path("C:/secret.txt") is None
    assert export_path("") is None
    assert export_path("   ") is None


def test_trusted_rows_and_verified_llm_only() -> None:
    assert counts_as_trusted(_issue(source="scanner", category="sec.secret"))
    assert counts_as_trusted(_issue(source="graph", category="graph.cycle"))
    assert counts_as_trusted(_issue(source="architecture", category="architecture.cut"))
    assert counts_as_trusted(_issue(source=None))
    assert counts_as_trusted(_issue(source="llm", locationVerified=True))
    assert not counts_as_trusted(_issue(source="llm", locationVerified=False))
    assert not counts_as_trusted(_issue(source="llm", locationVerified=None))
    assert not counts_as_trusted(_issue(source=None, category="sec.secret"))
