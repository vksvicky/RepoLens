"""Convert architecture DSL violations into Issue rows."""

from __future__ import annotations

from repolens.architecture.fas import candidate_feedback_arc_sets
from repolens.architecture.verify import BoundaryViolation
from repolens.graph.types import GraphResult
from repolens.schema import Issue, Severity


def boundary_violations_to_issues(
    violations: list[BoundaryViolation],
) -> list[Issue]:
    issues: list[Issue] = []
    for v in violations:
        line = v.edge.line if v.edge.line is not None and v.edge.line >= 1 else 1
        code = (v.edge.line_contents or "").strip() or (
            f"import {v.imported}  # from {v.importer}"
        )
        issues.append(
            Issue(
                severity=Severity.HIGH,
                priority="P3",
                category="arch.boundary_violation",
                file=_module_to_file(v.importer),
                line=line,
                title=(
                    f"Layer boundary breach: {v.from_boundary} → {v.to_boundary}"
                ),
                explanation=v.reason,
                impact=(
                    "Cross-layer imports erode hexagonal / clean-architecture "
                    "boundaries and make refactors and testing harder."
                ),
                recommendedFix=(
                    f"Remove or invert the dependency from {v.importer} to "
                    f"{v.imported} so {v.from_boundary} only imports "
                    f"allowed layers."
                ),
                codeExample=code,
                fixTiming="before launch",
                source="architecture",
            )
        )
    return issues


def fas_candidate_issues(result: GraphResult) -> list[Issue]:
    """Optional advisory finding summarizing FAS candidates (not auto-applied)."""
    candidates = candidate_feedback_arc_sets(result, max_candidates=3)
    if not candidates or result.cyclicity <= 0:
        return []
    best = candidates[0]
    preview = ", ".join(f"{e.importer}→{e.imported}(w={e.weight})" for e in best.edges)
    return [
        Issue(
            severity=Severity.MEDIUM,
            priority="P3",
            category="arch.fas_candidates",
            file=_module_to_file(best.edges[0].importer) if best.edges else "unknown",
            line=(best.edges[0].line or 1) if best.edges else 1,
            title="Weighted feedback-arc-set candidates available",
            explanation=(
                f"{len(candidates)} candidate cut set(s) would break runtime cycles "
                f"(cyclicity={result.cyclicity}). Lightest greedy cut: {preview}. "
                "Treat FAS as candidates — choose the cut that respects layer direction."
            ),
            impact=(
                "Blindly cutting the lightest edge can violate domain → adapter "
                "direction even when it mathematically breaks the cycle."
            ),
            recommendedFix=(
                "Review fasCandidates in the architecture remediation context and "
                "prefer cuts aligned with allowed_imports / hexagonal rules."
            ),
            codeExample=preview,
            fixTiming="before launch",
            source="architecture",
        )
    ]


def _module_to_file(module: str) -> str:
    return module.replace(".", "/") + ".py"
