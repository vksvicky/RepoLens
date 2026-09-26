"""Build LLM remediation context from violation subgraph + FAS candidates."""

from __future__ import annotations

import json
from typing import Any

from repolens.architecture.fas import FasCandidate, candidate_feedback_arc_sets
from repolens.architecture.verify import BoundaryViolation
from repolens.graph.types import GraphResult


def remediation_context(
    result: GraphResult,
    *,
    violations: list[BoundaryViolation] | None = None,
    max_candidates: int = 3,
) -> dict[str, Any]:
    """Structured payload for Slow Brain — subgraph + candidate cuts, not whole repo."""
    candidates = candidate_feedback_arc_sets(result, max_candidates=max_candidates)
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "architecture_remediation",
        "guidance": (
            "FAS candidates verify cycle-breaking only. Prefer cuts that respect "
            "stated layer / hexagonal direction (e.g. domain must not depend on "
            "adapters). Do not rubber-stamp the lightest edge."
        ),
        "cyclicity": result.cyclicity,
        "cycles": [
            {"modules": list(g.modules), "size": len(g.modules)}
            for g in result.cycles
            if len(g.modules) >= 2
        ],
        "fasCandidates": [_candidate_dict(c) for c in candidates],
        "boundaryViolations": [
            {
                "importer": v.importer,
                "imported": v.imported,
                "from": v.from_boundary,
                "to": v.to_boundary,
                "reason": v.reason,
                "line": v.edge.line,
                "lineContents": v.edge.line_contents,
            }
            for v in (violations or [])
        ],
    }
    return payload


def remediation_prompt_block(
    result: GraphResult,
    *,
    violations: list[BoundaryViolation] | None = None,
) -> str:
    ctx = remediation_context(result, violations=violations)
    return (
        "## Architecture violation subgraph (deterministic)\n\n"
        "Evaluate dependency **direction** against architecture principles. "
        "Weighted FAS rows are **candidate** cut options only.\n\n"
        "```json\n"
        + json.dumps(ctx, indent=2, sort_keys=True)
        + "\n```\n"
    )


def _candidate_dict(candidate: FasCandidate) -> dict[str, Any]:
    return {
        "label": candidate.label,
        "totalWeight": candidate.total_weight,
        "edges": [
            {
                "importer": e.importer,
                "imported": e.imported,
                "weight": e.weight,
                "line": e.line,
                "lineContents": e.line_contents,
            }
            for e in candidate.edges
        ],
    }
