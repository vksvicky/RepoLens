"""Phase 6.9: deterministic package usage hints (not reachability)."""

from __future__ import annotations

from pathlib import Path

from repolens.schema import Issue, Severity
from repolens.scanners.usage_hints import apply_usage_hints, package_referenced_in_tree


def _sca(pkg: str = "requests") -> Issue:
    return Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="osv",
        file="poetry.lock",
        line=1,
        title=f"CVE-2024-1 in {pkg}",
        explanation="x",
        impact="Attacker may exploit this.",
        recommendedFix="upgrade",
        codeExample="# upgrade",
        source="scanner",
        packageName=pkg,
        advisoryId="CVE-2024-1",
    )


def test_package_referenced_in_import(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import requests\n", encoding="utf-8")
    assert package_referenced_in_tree(tmp_path, "requests") is True
    assert package_referenced_in_tree(tmp_path, "notapkg") is False


def test_apply_usage_hints_sets_labels(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("from requests import get\n", encoding="utf-8")
    out = apply_usage_hints(tmp_path, [_sca("requests"), _sca("unusedlib")])
    assert out[0].usageHint == "referenced_in_source"
    assert out[1].usageHint == "no_reference_found"
