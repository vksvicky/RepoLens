"""Architecture DSL load/verify + weighted FAS (G4)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.architecture import (
    ArchitectureDoc,
    Boundary,
    candidate_feedback_arc_sets,
    load_architecture,
    match_boundary,
    remediation_context,
    verify_boundaries,
)
from repolens.cli import app
from repolens.graph import analyse_python_graph

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
CYCLE_PKG = FIXTURES / "graph_cycle_pkg"


def test_match_boundary_glob() -> None:
    b = Boundary(name="domain", path="packcycle/**", allowed_imports=[])
    assert match_boundary("packcycle.a", b)
    assert match_boundary("packcycle.b", b)
    assert not match_boundary("other.x", b)


def test_load_architecture_yaml(tmp_path: Path) -> None:
    path = tmp_path / "repolens.yaml"
    path.write_text(
        """
schemaVersion: 1
boundaries:
  - name: a_layer
    path: packcycle/a*
    allowed_imports: []
  - name: b_layer
    path: packcycle/b*
    allowed_imports: [a_layer]
""",
        encoding="utf-8",
    )
    doc = load_architecture(path)
    assert len(doc.boundaries) == 2
    assert doc.boundaries[1].allowed_imports == ["a_layer"]


def test_verify_boundaries_on_cycle_fixture() -> None:
    result = analyse_python_graph(CYCLE_PKG)
    assert result.cyclicity > 0
    doc = ArchitectureDoc(
        schemaVersion=1,
        boundaries=[
            Boundary(name="a_layer", path="packcycle/a*", allowed_imports=[]),
            Boundary(
                name="b_layer", path="packcycle/b*", allowed_imports=["a_layer"]
            ),
        ],
    )
    violations = verify_boundaries(result, doc)
    # a→b is forbidden (a_layer allowed_imports=[]); b→a is allowed
    assert any(v.from_boundary == "a_layer" and v.to_boundary == "b_layer" for v in violations)
    assert not any(
        v.from_boundary == "b_layer" and v.to_boundary == "a_layer" for v in violations
    )


def test_fas_candidates_break_cycle() -> None:
    result = analyse_python_graph(CYCLE_PKG)
    candidates = candidate_feedback_arc_sets(result)
    assert candidates
    assert candidates[0].total_weight >= 1
    assert candidates[0].edges


def test_remediation_context_includes_guidance() -> None:
    result = analyse_python_graph(CYCLE_PKG)
    ctx = remediation_context(result, violations=[])
    assert "candidate" in ctx["guidance"].lower() or "FAS" in ctx["guidance"]
    assert ctx["fasCandidates"]
    assert ctx["cyclicity"] == result.cyclicity


def test_check_architecture_cli_fails_on_violation(tmp_path: Path) -> None:
    # Copy minimal cycle package into tmp with architecture yaml
    pkg = tmp_path / "packcycle"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from packcycle import b  # noqa\n", encoding="utf-8")
    (pkg / "b.py").write_text("from packcycle import a  # noqa\n", encoding="utf-8")
    (tmp_path / "repolens.yaml").write_text(
        """
schemaVersion: 1
boundaries:
  - name: a_layer
    path: packcycle/a*
    allowed_imports: []
  - name: b_layer
    path: packcycle/b*
    allowed_imports: [a_layer]
""",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", "architecture", "--path", str(tmp_path)])
    assert result.exit_code == 1, result.output
    assert "Boundary violations" in result.output or "FAIL" in result.output


def test_check_architecture_cli_json(tmp_path: Path) -> None:
    pkg = tmp_path / "okpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "repolens.yaml").write_text(
        """
schemaVersion: 1
boundaries:
  - name: core
    path: okpkg/**
    allowed_imports: []
""",
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["check", "architecture", "--path", str(tmp_path), "--json"]
    )
    assert result.exit_code == 0, result.output
    assert "fasCandidates" in result.output
