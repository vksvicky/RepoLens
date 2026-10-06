"""Deterministic architecture boundary verification against the import graph."""

from __future__ import annotations

from dataclasses import dataclass

from repolens.architecture.match import match_boundary, module_path_form
from repolens.architecture.schema import ArchitectureDoc, Boundary
from repolens.graph.types import GraphResult, ImportEdge

WILDCARD = "*"

__all__ = [
    "BoundaryViolation",
    "WILDCARD",
    "boundary_for_module",
    "legal_import_boundaries",
    "match_boundary",
    "module_path_form",
    "verify_boundaries",
]


@dataclass(frozen=True)
class BoundaryViolation:
    importer: str
    imported: str
    from_boundary: str
    to_boundary: str
    edge: ImportEdge
    reason: str


def boundary_for_module(module: str, doc: ArchitectureDoc) -> Boundary | None:
    for boundary in doc.boundaries:
        if match_boundary(module, boundary):
            return boundary
    return None


def verify_boundaries(
    result: GraphResult, doc: ArchitectureDoc
) -> list[BoundaryViolation]:
    """Return gated import edges that violate allow/forbid rules between layers."""
    if not doc.boundaries:
        return []
    allowed_by_name = {b.name: set(b.allowed_imports) for b in doc.boundaries}
    forbidden_by_name = {b.name: set(b.forbidden_imports) for b in doc.boundaries}
    violations: list[BoundaryViolation] = []
    for edge in result.gated_edges:
        src = boundary_for_module(edge.importer, doc)
        dst = boundary_for_module(edge.imported, doc)
        if src is None or dst is None:
            if doc.strict:
                missing = edge.importer if src is None else edge.imported
                violations.append(
                    BoundaryViolation(
                        importer=edge.importer,
                        imported=edge.imported,
                        from_boundary=src.name if src else "",
                        to_boundary=dst.name if dst else "",
                        edge=edge,
                        reason=f"unmapped module {missing} under strict architecture",
                    )
                )
            continue
        if src.name == dst.name:
            continue
        forbidden = forbidden_by_name.get(src.name, set())
        allowed = allowed_by_name.get(src.name, set())
        if dst.name in forbidden:
            violations.append(
                BoundaryViolation(
                    importer=edge.importer,
                    imported=edge.imported,
                    from_boundary=src.name,
                    to_boundary=dst.name,
                    edge=edge,
                    reason=(
                        f"Boundary {src.name!r} may not import {dst.name!r} "
                        f"(forbidden_imports={sorted(forbidden)})"
                    ),
                )
            )
            continue
        if WILDCARD in allowed:
            continue
        if dst.name in allowed:
            continue
        violations.append(
            BoundaryViolation(
                importer=edge.importer,
                imported=edge.imported,
                from_boundary=src.name,
                to_boundary=dst.name,
                edge=edge,
                reason=(
                    f"Boundary {src.name!r} may not import {dst.name!r} "
                    f"(allowed_imports={sorted(allowed)})"
                ),
            )
        )
    return violations


def legal_import_boundaries(module: str, doc: ArchitectureDoc) -> list[str]:
    """Names of boundaries *module* may import from (empty if unknown module)."""
    src = boundary_for_module(module, doc)
    if src is None:
        return []
    return list(src.allowed_imports)
