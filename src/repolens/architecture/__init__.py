"""Architecture DSL + weighted FAS remediation (G4)."""

from repolens.architecture.fas import (
    FasCandidate,
    WeightedEdge,
    candidate_feedback_arc_sets,
    edge_weights,
    violation_subgraph_edges,
)
from repolens.architecture.issues import (
    boundary_violations_to_issues,
    fas_candidate_issues,
)
from repolens.architecture.load import (
    ArchitectureLoadError,
    discover_architecture_path,
    load_architecture,
)
from repolens.architecture.remediation import (
    remediation_context,
    remediation_prompt_block,
)
from repolens.architecture.schema import ArchitectureDoc, Boundary, architecture_json_schema
from repolens.architecture.verify import (
    BoundaryViolation,
    boundary_for_module,
    legal_import_boundaries,
    match_boundary,
    verify_boundaries,
)

__all__ = [
    "ArchitectureDoc",
    "ArchitectureLoadError",
    "Boundary",
    "BoundaryViolation",
    "FasCandidate",
    "WeightedEdge",
    "architecture_json_schema",
    "boundary_for_module",
    "boundary_violations_to_issues",
    "candidate_feedback_arc_sets",
    "discover_architecture_path",
    "edge_weights",
    "fas_candidate_issues",
    "legal_import_boundaries",
    "load_architecture",
    "match_boundary",
    "remediation_context",
    "remediation_prompt_block",
    "verify_boundaries",
    "violation_subgraph_edges",
]
