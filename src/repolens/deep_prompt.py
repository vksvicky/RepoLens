"""Deep pass prompt builder."""

from __future__ import annotations

from collections.abc import Iterable

from repolens.deep_types import DeepPass
from repolens.prose import BRITISH_ENGLISH_INSTRUCTION
from repolens.rules.registry import Rule

_COVERAGE_CONTRACT = (
    "Coverage contract: for each coverage id listed below, either emit one or "
    "more FindingReport issues that address it, or add a durabilityGaps entry "
    "of the form `coverage:<id>: N/A — <reason>`."
)


def build_deep_prompt(
    deep_pass: DeepPass,
    rules: list[Rule],
    coverage_ids: Iterable[str],
    *,
    pack_ids: list[str] | None = None,
) -> str:
    """Concatenate enabled rule bodies for the pass plus the coverage contract."""
    from repolens.packs.registry import pack_playbook_sections

    by_id = {r.id: r for r in rules}
    sections: list[str] = [
        f"Deep pass: {deep_pass.name}",
        f"Rule ids: {', '.join(deep_pass.rule_ids)}",
        "",
    ]
    for rule_id in deep_pass.rule_ids:
        rule = by_id.get(rule_id)
        if rule is None or not rule.enabled:
            continue
        sections.append(f"## Rule: {rule.title} ({rule.id})")
        sections.append(rule.body)
        sections.append("")
    for label, content in pack_playbook_sections(pack_ids or []):
        sections.append(f"## Playbook: {label}")
        sections.append(content)
        sections.append("")

    cov_list = list(coverage_ids)
    sections.append("## Coverage ids")
    sections.append(_COVERAGE_CONTRACT)
    if cov_list:
        for cov_id in cov_list:
            sections.append(f"- {cov_id}")
    else:
        sections.append("(none)")
    sections.append("")
    sections.append(BRITISH_ENGLISH_INSTRUCTION)
    sections.append(
        "Analyse using the rules and coverage contract. Return FindingReport JSON only."
    )
    return "\n".join(sections)
