"""Explain diagrams, next-step text, and markdown rendering."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repolens.explain import ExplainDoc, ExplainSolution

from repolens.diagrams import normalize_mermaid_node_ids, process_diagram
from repolens.report import render_code_example_fenced
from repolens.schema import Issue

_REMOVED_IMPORT_RE = re.compile(
    r"^-\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", re.MULTILINE
)
# Packages / modules that are almost never safe to strip from a CLI host file.
_PROTECTED_IMPORT_ROOTS = frozenset(
    {
        "typer",
        "pathlib",
        "typing",
        "collections",
        "dataclasses",
        "enum",
        "functools",
        "itertools",
        "json",
        "os",
        "re",
        "sys",
        "httpx",
        "pydantic",
        "rich",
        "click",
    }
)


def import_diff_risk_notes(diff: str) -> list[str]:
    """Warn when a diff deletes imports the remaining file likely still needs."""
    if not diff.strip():
        return []
    removed: list[str] = []
    for match in _REMOVED_IMPORT_RE.finditer(diff):
        raw = (match.group(1) or match.group(2) or "").strip().strip("'\"")
        root = raw.split(".", 1)[0]
        if root in _PROTECTED_IMPORT_ROOTS or raw.startswith("repolens."):
            removed.append(raw)
    if not removed:
        return []
    uniq = sorted(set(removed))
    return [
        "Caution: this diff **removes** imports that the host file may still "
        f"need ({', '.join(f'`{x}`' for x in uniq)}). Prefer additive imports "
        "and thin wrappers — do not wipe `typer` / stdlib / framework imports "
        "from the registration module."
    ]


def sanitize_explain_mermaid(body: str) -> str:
    """Compatibility wrapper — normalize dotted Mermaid node ids."""
    return normalize_mermaid_node_ids(body)


_MOVE_RE = re.compile(
    r"^(?P<symbol>[^\s(]+)"
    r"(?:\s*\([^)]*\))?"  # optional (lines …)
    r"\s*(?:→|->|=>)\s*"
    r"(?P<target>\S+?)\s*$"
)


def parse_move(move: str) -> tuple[str, str] | None:
    """Parse ``symbol (lines A–B) → target.py`` into (symbol, target)."""
    text = (move or "").strip().strip("`")
    if not text:
        return None
    m = _MOVE_RE.match(text)
    if not m:
        return None
    return m.group("symbol").strip(), m.group("target").strip()


def _host_module_stem(file_path: str) -> str:
    name = Path(file_path.replace("\\", "/")).name
    return name[:-3] if name.endswith(".py") else name


def build_diagram_from_moves(
    *,
    host_file: str,
    moves: list[str],
    plan_title: str = "",
) -> str:
    """Diagram that matches the actionable plan — Mermaid safe + rich legend.

    IDE Markdown previews corrupt labelled Mermaid nodes, so the fence uses
    bare ids only. The ASCII map + table carry the same detail as the Moves
    list (symbols, targets) so the diagram section matches the explain body.
    """
    parsed: list[tuple[str, str]] = []
    for raw in moves:
        pair = parse_move(raw)
        if pair:
            parsed.append(pair)
    if not parsed:
        return ""

    host = _host_module_stem(host_file)
    host_id = re.sub(r"[^A-Za-z0-9_]", "_", host) or "host"
    # ``---`` not ``-->``: Cursor Markdown preview treats ``>`` as blockquote
    # and leaves a useless ``host--`` node.
    lines_mmd = ["flowchart TD"]
    legend_rows: list[str] = [
        "| Node | From symbol | Into module |",
        "|------|-------------|-------------|",
        f"| `{host_id}` | *(host file)* | `{host_file}` |",
    ]
    ascii_lines = [
        "Split plan (same as solution 1 moves):",
        f"{host_file}  (host — keep as thin shell / re-exports)",
    ]
    for symbol, target in parsed:
        target_stem = Path(target.replace("\\", "/")).name
        if target_stem.endswith(".py"):
            target_stem = target_stem[:-3]
        tid = re.sub(r"[^A-Za-z0-9_]", "_", target_stem) or "mod"
        lines_mmd.append(f"{host_id}---{tid}")
        legend_rows.append(f"| `{tid}` | `{symbol}` | `{target}` |")
        ascii_lines.append(f"  ├─ extract `{symbol}`  →  new file `{target}`")

    if len(ascii_lines) > 2:
        ascii_lines[-1] = ascii_lines[-1].replace("  ├─", "  └─", 1)

    title = plan_title.strip() or "Primary refactor plan"
    # ASCII first: it carries the meaning. Mermaid is topology-only (no labels
    # survive IDE previews), so it must not be the primary explanation.
    parts = [
        f"_Diagram for: **{title}** (same moves as solution 1)_",
        "",
        "```",
        "\n".join(ascii_lines),
        "```",
        "",
        *legend_rows,
        "",
        "_Topology sketch (node ids only — see table above for meaning):_",
        "",
        "```mermaid",
        "\n".join(lines_mmd),
        "```",
        "",
    ]
    return "\n".join(parts)


def _degraded_doc(issue: Issue, *, error: str, outline: str = "") -> ExplainDoc:
    from repolens.explain import ExplainDoc, ExplainSolution
    moves: list[str] = []
    if outline:
        # Pull first few `function`/`class` lines as hints for the human
        for line in outline.splitlines():
            if line.startswith("- ") and "`" in line:
                moves.append(line.lstrip("- ").strip())
            if len(moves) >= 4:
                break
    return ExplainDoc(
        problem=(
            f"{issue.explanation or issue.title} "
            f"(explain degraded: {error}. Outline preserved below in solutions.)"
        ),
        impact=issue.impact or "(not provided)",
        solutions=[
            ExplainSolution(
                title="Split using the real symbols in the outline",
                tradeoffs="Manual, but avoids hallucinated module names.",
                impactEffort="High impact when the file is a true mega-file",
                moves=moves
                or [
                    "Open the file and extract the largest function/class first"
                ],
                importDiff=(
                    "# After extracting, update imports, e.g.:\n"
                    f"# + from … import {issue.file.split('/')[-1].removesuffix('.py')}_part\n"
                ),
            ),
            ExplainSolution(
                title="Apply the finding's recommended fix",
                tradeoffs=issue.recommendedFix or "See gate report.",
                impactEffort="Depends on finding",
            ),
        ],
        diagramMermaid=(
            "flowchart TD\n"
            f"  A[{issue.file}] --> B[Extract largest symbol first]"
        ),
        nextStep=issue.recommendedFix
        or "Extract the largest symbol from the outline into its own module.",
    )


def _select_plan_moves(doc: ExplainDoc) -> tuple[str, list[str]]:
    """Prefer the first solution that has concrete moves."""
    for sol in doc.solutions:
        if sol.moves:
            return sol.title, list(sol.moves)
    return "", []


_VAGUE_NEXT_STEP = (
    "into separate module",
    "update import",
    "accordingly",
    "evaluate structure",
    "consider refactor",
    "as appropriate",
)


def _mentions_token(haystack: str, token: str) -> bool:
    """Whole-token match so ``review`` does not hit ``commands_review``."""
    tok = (token or "").strip()
    if len(tok) < 2:
        return False
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(tok)}(?![A-Za-z0-9_])"
    return re.search(pattern, haystack, re.I) is not None


def next_step_is_vague(text: str, moves: list[str]) -> bool:
    """True when nextStep lacks symbol/target detail from the plan moves."""
    t = (text or "").strip()
    if not t:
        return True
    if "→" in t or "->" in t or "=>" in t:
        return False
    lower = t.lower()
    for raw in moves:
        pair = parse_move(raw)
        if not pair:
            if raw.strip() and _mentions_token(t, raw.strip()):
                return False
            continue
        symbol, target = pair
        if _mentions_token(t, symbol):
            return False
        stem = Path(target.replace("\\", "/")).name
        if _mentions_token(t, stem) or _mentions_token(t, stem.removesuffix(".py")):
            return False
    if any(marker in lower for marker in _VAGUE_NEXT_STEP):
        return True
    if lower.startswith("refactor") and len(t) < 180:
        return True
    return len(t) < 48


def build_recommended_next_step(
    *,
    next_step: str,
    host_file: str,
    plan_title: str = "",
    moves: list[str],
    fallback: str = "",
) -> str:
    """Concrete ordered checklist from moves; never a vague one-liner alone."""
    lead = (next_step or "").strip()
    vague = next_step_is_vague(lead, moves)
    if not moves:
        return lead or (fallback or "").strip() or "_n/a_"

    lines: list[str] = []
    title = plan_title.strip()
    if title:
        lines.append(f"Prefer **{title}**. Work in this order:")
    else:
        lines.append("Work in this order:")
    lines.append("")
    for i, mv in enumerate(moves, start=1):
        pair = parse_move(mv)
        if pair:
            symbol, target = pair
            lines.append(
                f"{i}. Extract `{symbol}` from `{host_file}` into `{target}` "
                f"— `{mv}`."
            )
        else:
            lines.append(f"{i}. {mv}")
    n = len(moves)
    lines.append(
        f"{n + 1}. Keep `{host_file}` as a thin shell: **additive** imports / "
        "re-exports; do **not** strip `typer` or other registration imports."
    )
    lines.append(
        f"{n + 2}. Re-run the relevant tests and `repolens review` on the "
        "touched paths."
    )
    checklist = "\n".join(lines)
    if lead and not vague:
        return f"{lead}\n\n{checklist}"
    return checklist


def _render_meta_section(
    issue: Issue, uuid: str, provider: str | None, model: str | None, duration_seconds: float | None
) -> list[str]:
    fp = issue.stableId or ""
    occ = issue.runId or ""
    meta = [
        f"# Explain — {issue.title}",
        "",
    ]
    if fp:
        meta.append(f"**Fingerprint:** `{fp}`  ")
    if occ:
        meta.append(f"**Occurrence:** `{occ}`  ")
    meta.append(f"**Lookup UUID:** `{uuid}`  ")
    meta.extend(
        [
            f"**File:** `{issue.file}:{issue.line}`  ",
            f"**Severity:** {issue.severity.value}  ",
            f"**Category:** {issue.category}  ",
        ]
    )
    if issue.source:
        meta.append(f"**Source:** {issue.source}  ")
    if provider or model:
        meta.append(
            f"**Model:** `{model or '?'}` via `{provider or '?'}`  "
        )
    if duration_seconds is not None:
        meta.append(f"**Duration:** {duration_seconds:.0f}s  ")
    return meta

def _render_solutions_section(solutions: list[ExplainSolution]) -> list[str]:
    meta = ["## Actionable solutions", ""]
    if not solutions:
        meta.append("_No solutions returned; see recommended fix on the issue._")
    for i, sol in enumerate(solutions, start=1):
        head = sol.title
        if sol.impactEffort.strip():
            head = f"{sol.title} ({sol.impactEffort.strip()})"
        meta.append(f"{i}. **{head}**")
        if sol.tradeoffs.strip():
            meta.append(f"   - {sol.tradeoffs.strip()}")
        if sol.moves:
            meta.append("   - **Moves:**")
            for mv in sol.moves:
                meta.append(f"     - `{mv}`" if "`" not in mv else f"     - {mv}")
        if sol.importDiff.strip():
            meta.append("   - **Import / call-site diff:**")
            meta.append("")
            for line in render_code_example_fenced(sol.importDiff.strip()):
                meta.append(line)
            for note in import_diff_risk_notes(sol.importDiff):
                meta.append("")
                meta.append(f"   > {note}")
            meta.append("")
    return meta

def _render_proposed_refactor(doc: ExplainDoc) -> list[str]:
    meta = []
    if doc.proposedRefactorDiff.strip():
        meta.extend(["## Proposed refactor", ""])
        for line in render_code_example_fenced(doc.proposedRefactorDiff.strip()):
            meta.append(line)
        for note in import_diff_risk_notes(doc.proposedRefactorDiff):
            meta.append("")
            meta.append(f"> {note}")
        meta.append("")
    return meta

def render_explain_markdown(
    *,
    issue: Issue,
    doc: ExplainDoc,
    diagram_block: str,
    uuid: str,
    outline: str = "",
    provider: str | None = None,
    model: str | None = None,
    duration_seconds: float | None = None,
) -> str:
    meta = _render_meta_section(issue, uuid, provider, model, duration_seconds)
    meta.extend(["", "## Problem", "", doc.problem.strip() or issue.explanation, ""])
    if doc.impact.strip():
        meta.extend(["## Impact", "", doc.impact.strip(), ""])
    if outline.strip():
        meta.extend(
            [
                "## Structure used as evidence",
                "",
                "```",
                outline.strip(),
                "```",
                "",
            ]
        )
    
    meta.extend(_render_solutions_section(doc.solutions or []))
    meta.extend(_render_proposed_refactor(doc))
    
    plan_title, plan_moves = _select_plan_moves(doc)
    grounded = build_diagram_from_moves(
        host_file=issue.file,
        moves=plan_moves,
        plan_title=plan_title,
    )
    diagram_section = grounded or diagram_block or "_No diagram._"
    next_step = build_recommended_next_step(
        next_step=doc.nextStep,
        host_file=issue.file,
        plan_title=plan_title,
        moves=plan_moves,
        fallback=issue.recommendedFix or "",
    )
    meta.extend(
        [
            "## Diagram",
            "",
            diagram_section,
            "",
            "## Recommended next step",
            "",
            next_step,
            "",
        ]
    )
    return "\n".join(meta)


def _process_diagram_block(
    want_diagram: bool,
    render_mode: str,
    doc: ExplainDoc,
    report_out: Path,
) -> str:
    if not want_diagram:
        return "_Diagram skipped._"

    mermaid_in = sanitize_explain_mermaid(
        doc.diagramMermaid or "flowchart LR\n  A --> B"
    )
    diag = process_diagram(
        mermaid_in,
        render_image=render_mode,
        out_dir=report_out / "explain-assets",
    )
    if diag.kind == "mermaid" and diag.mermaid:
        diagram_block = f"```mermaid\n{diag.mermaid}\n```"
        notes = list(diag.notes)
        if not diag.image_path:
            notes.append(
                "optional PNG/SVG not generated — Mermaid fence above still "
                "previews in GitHub/IDE (`diagram.render_skipped` is not a failure)"
            )
        if notes:
            diagram_block += "\n\n_" + "; ".join(dict.fromkeys(notes)) + "_"
        if diag.image_path:
            diagram_block += f"\n\n![diagram]({diag.image_path})"
        return diagram_block
    else:
        diagram_block = f"```\n{diag.textual or ''}\n```"
        if diag.notes:
            diagram_block += "\n\n_" + "; ".join(diag.notes) + "_"
        return diagram_block
