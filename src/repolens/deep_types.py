"""Deep pass types and small shared helpers.

Char budgeting uses ``FileEntry.size`` (bytes) as a character-cost estimate so
planning does not read file contents. Callers that later pack prompts should
still use ``read_excerpt`` (or the same size estimate) consistently with this
budget so selected files fit the pass cap.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from repolens.inventory import FileEntry
from repolens.prose import BRITISH_ENGLISH_INSTRUCTION
from repolens.schema import FindingReport

_COVERAGE_LINE_SHAPE = (
    "coverage:<id>: N/A — <one fact that is true in this repository>"
)

_MODULE_SUFFIXES = (
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".cs",
    ".kt",
    ".java",
)


@dataclass(frozen=True)
class DeepPass:
    name: str
    rule_ids: list[str]
    coverage_ids: list[str]
    files: list[FileEntry]
    pack_mode: str = "full"  # full | outline | hybrid
    file_pack_modes: dict[str, str] = field(default_factory=dict)


def coverage_checklist_tail(coverage_ids: Iterable[str]) -> str:
    """Restate the checklist after the source files so a large pack cannot bury it."""
    ids = [cid for cid in coverage_ids if cid]
    if not ids:
        return ""
    lines = [
        "",
        "## Coverage checklist (required before JSON)",
        "Account for every id below. For an id with no finding, add one line",
        "in this shape, using that id and a fact from this repository:",
        _COVERAGE_LINE_SHAPE,
        "Do not copy a fact from another repository.",
        "A line without the coverage: prefix, or a reason that says “not reviewed”,",
        "does not count and lowers the gate.",
    ]
    lines.extend(f"- {cid}" for cid in ids)
    return "\n".join(lines)


def coverage_closure_prompt(missed_ids: Iterable[str]) -> str:
    """Ask only for checklist ids the earlier passes left unanswered."""
    ids = [cid for cid in missed_ids if cid]
    lines = [
        "Coverage closure. Earlier passes left these checklist ids unanswered.",
        "For each id, either emit an issue whose category is that id, or one",
        "line in this shape, using that id and a fact from this repository:",
        _COVERAGE_LINE_SHAPE,
        "Do not copy a fact from another repository.",
        "A reason that says 'not reviewed' is rejected and the id stays missed.",
        "Return FindingReport JSON only.",
        "",
    ]
    lines.extend(f"- {cid}" for cid in ids)
    lines.append("")
    lines.append(BRITISH_ENGLISH_INSTRUCTION)
    return "\n".join(lines)


def module_name_forms(name: str) -> set[str]:
    """Normalize a module or path into comparable dotted/path forms."""
    n = name.strip().replace("\\", "/")
    if not n:
        return set()
    forms: set[str] = {n, n.replace("/", ".")}
    for suf in _MODULE_SUFFIXES:
        if n.endswith(suf):
            stem = n[: -len(suf)]
            forms.add(stem)
            forms.add(stem.replace("/", "."))
            n = stem
            break
    # Drop a leading ``src.`` / ``src/`` so ``src/pkg/a.py`` matches ``pkg.a``.
    extras: set[str] = set()
    for form in list(forms):
        dotted = form.replace("/", ".")
        forms.add(dotted)
        if dotted.startswith("src."):
            extras.add(dotted[4:])
        if form.startswith("src/"):
            extras.add(form[4:])
            extras.add(form[4:].replace("/", "."))
    forms |= extras
    return {f for f in forms if f}


def entry_matches_cycle(entry: FileEntry, cycle_modules: set[str]) -> bool:
    entry_forms = module_name_forms(entry.relative)
    for mod in cycle_modules:
        mod_forms = module_name_forms(mod)
        if entry_forms & mod_forms:
            return True
        for ef in entry_forms:
            for mf in mod_forms:
                if ef == mf or ef.endswith("." + mf) or mf.endswith("." + ef):
                    return True
    return False


def estimate_outline_chars(entry: FileEntry) -> int:
    """Char-cost estimate for an outline pack without reading the file.

    Outlines are typically far smaller than raw bodies; using ``entry.size``
    would empty a P3 budget after a handful of large modules.
    """
    approx_lines = max(1, entry.size // 40)
    return max(80, min(entry.size, approx_lines * 30 // 8))


def compact_pass_summary(
    report: FindingReport, *, max_chars: int = 800
) -> str:
    """≤~200-token summary of findings for the next deep pass."""
    lines = ["Confirmed findings from the prior Slow Brain pass:"]
    for issue in report.issues[:12]:
        sev = getattr(issue.severity, "value", issue.severity)
        lines.append(f"- [{sev}] {issue.title} ({issue.file}:{issue.line})")
    if not report.issues:
        lines.append("- (no findings)")
    covered = [
        gap for gap in report.durabilityGaps if gap.startswith("coverage:")
    ][:8]
    if covered:
        lines.append("Coverage notes:")
        lines.extend(f"- {gap}" for gap in covered)
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"
