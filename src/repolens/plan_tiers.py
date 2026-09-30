"""Quick-win versus structural rows for Plan to fix."""

from __future__ import annotations

from collections.abc import Sequence

from repolens.schema import Issue

_STRUCTURAL_CATEGORIES = frozenset(
    {
        "heuristic.mega_file",
        "heuristic.sibling_duplication",
        "graph.cycle",
        "arch.structure_size",
    }
)


def is_structural(issue: Issue) -> bool:
    """A mega-file, clone, cycle, or layer breach is structural work."""
    if issue.title.startswith("High complexity:"):
        return False
    return issue.category in _STRUCTURAL_CATEGORIES


def _issue_line(issue: Issue) -> str:
    return (
        f"1. **{issue.title}** (`{issue.file}:{issue.line}`) — "
        f"{issue.recommendedFix}"
    )


def render_plan_tiers(
    immediate: Sequence[Issue],
    hotspots: Sequence[object],
) -> list[str]:
    """Headings only. No hour estimates."""
    quick = [issue for issue in immediate if not is_structural(issue)]
    structural = [issue for issue in immediate if is_structural(issue)]
    lines: list[str] = []
    if quick:
        lines.append("Quick wins:")
        lines.append("")
        lines.extend(_issue_line(issue) for issue in quick)
        lines.append("")
    if structural or hotspots:
        lines.append("Structural:")
        lines.append("")
    if structural:
        lines.extend(_issue_line(issue) for issue in structural)
        lines.append("")
    if hotspots:
        lines.append("Complexity to simplify:")
        lines.append("")
        for row in hotspots:
            lines.append(
                f"1. `{row.function}` (`{row.file}:{row.line}`) — "
                f"cyclomatic {row.cyclomatic}, cognitive {row.cognitive}. "
                "Extract helpers or replace deep conditionals with early returns, "
                "then re-measure."
            )
        lines.append("")
    if not quick and not structural and not hotspots:
        lines.extend(["_No immediate-priority findings._", ""])
    return lines
