"""#96 strict architecture DSL: forbid, wildcard, strict unmapped, schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repolens.architecture import (
    ArchitectureDoc,
    ArchitectureLoadError,
    Boundary,
    architecture_json_schema,
    legal_import_boundaries,
    load_architecture,
    verify_boundaries,
)
from repolens.graph.types import (
    EdgeKind,
    GraphResult,
    GraphStatus,
    ImportEdge,
    ImportScope,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "repolens"
    / "architecture"
    / "schemas"
    / "architecture.schema.json"
)


def _edge(importer: str, imported: str) -> ImportEdge:
    return ImportEdge(
        importer=importer,
        imported=imported,
        kind=EdgeKind.RUNTIME,
        scope=ImportScope.MODULE,
        line=1,
    )


def _graph(*pairs: tuple[str, str]) -> GraphResult:
    edges = [_edge(a, b) for a, b in pairs]
    return GraphResult(
        status=GraphStatus.OK,
        edges=edges,
        gated_edges=edges,
    )


def test_forbidden_only_does_not_open_layer() -> None:
    doc = ArchitectureDoc(
        schemaVersion=2,
        boundaries=[
            Boundary(
                name="services",
                path="src/services/**",
                forbidden_imports=["presentation"],
            ),
            Boundary(name="domain", path="src/domain/**"),
            Boundary(name="presentation", path="src/presentation/**"),
        ],
    )
    result = _graph(("src/services/api", "src/domain/model"))
    violations = verify_boundaries(result, doc)
    assert any(v.to_boundary == "domain" for v in violations)


def test_wildcard_allows_except_forbidden() -> None:
    doc = ArchitectureDoc(
        schemaVersion=2,
        boundaries=[
            Boundary(
                name="services",
                path="src/services/**",
                allowed_imports=["*"],
                forbidden_imports=["presentation"],
            ),
            Boundary(name="domain", path="src/domain/**"),
            Boundary(name="presentation", path="src/presentation/**"),
        ],
    )
    result = _graph(
        ("src/services/api", "src/domain/model"),
        ("src/services/api", "src/presentation/view"),
    )
    violations = verify_boundaries(result, doc)
    assert not any(v.to_boundary == "domain" for v in violations)
    assert any(v.to_boundary == "presentation" for v in violations)


def test_forbid_wins_over_allow() -> None:
    doc = ArchitectureDoc(
        boundaries=[
            Boundary(
                name="api",
                path="src/api/**",
                allowed_imports=["domain", "db"],
                forbidden_imports=["db"],
            ),
            Boundary(name="domain", path="src/domain/**"),
            Boundary(name="db", path="src/db/**"),
        ]
    )
    result = _graph(("src/api/h", "src/db/t"))
    violations = verify_boundaries(result, doc)
    assert any(v.to_boundary == "db" for v in violations)


def test_strict_flags_unmapped_module() -> None:
    doc = ArchitectureDoc(
        strict=True,
        boundaries=[
            Boundary(name="domain", path="src/domain/**", allowed_imports=[]),
        ],
    )
    result = _graph(("src/domain/m", "src/orphan/x"))
    violations = verify_boundaries(result, doc)
    assert violations
    assert "unmapped" in violations[0].reason


def test_non_strict_skips_unmapped() -> None:
    doc = ArchitectureDoc(
        strict=False,
        boundaries=[
            Boundary(name="domain", path="src/domain/**", allowed_imports=[]),
        ],
    )
    result = _graph(("src/domain/m", "src/orphan/x"))
    assert verify_boundaries(result, doc) == []


def test_quoted_no_layer_name_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "repolens.yaml"
    path.write_text(
        'schemaVersion: 2\nboundaries:\n  - name: "NO"\n    path: src/no/**\n',
        encoding="utf-8",
    )
    doc = load_architecture(path)
    assert doc.boundaries[0].name == "NO"


def test_unknown_keys_rejected(tmp_path: Path) -> None:
    path = tmp_path / "architecture.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "boundaries": [{"name": "a", "path": "a/**", "mystery": True}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArchitectureLoadError):
        load_architecture(path)


def test_packaged_schema_matches_pydantic_model() -> None:
    packaged = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert packaged == architecture_json_schema()


def test_legal_imports_unknown_module() -> None:
    doc = ArchitectureDoc(boundaries=[Boundary(name="d", path="src/d/**")])
    assert legal_import_boundaries("nope", doc) == []
    assert legal_import_boundaries("src/d/x", doc) == []
