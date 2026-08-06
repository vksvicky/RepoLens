"""Per-issue explain deep-dives (Phase 6)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from repolens.config import RepoLensConfig, load_config, resolve_report_dir
from repolens.diagrams import process_diagram
from repolens.llm import LlmError, analyze_raw
from repolens.schema import FindingReport, Issue

_LAST_REPORT_NAME = "last_report.json"
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class ExplainDisabledError(RuntimeError):
    """Raised when ``[explain].enabled`` is false."""


class IssueNotFoundError(LookupError):
    """Raised when no issue matches the given UUID."""


class ExplainSolution(BaseModel):
    title: str
    tradeoffs: str = ""


class ExplainDoc(BaseModel):
    problem: str
    impact: str = ""
    solutions: list[ExplainSolution] = Field(default_factory=list)
    diagramMermaid: str = ""
    nextStep: str = ""


def write_last_report_pointer(project_root: Path, report_json: Path) -> Path:
    """Record the latest JSON report path under ``.repolens/``."""
    meta_dir = project_root / ".repolens"
    meta_dir.mkdir(parents=True, exist_ok=True)
    pointer = meta_dir / _LAST_REPORT_NAME
    payload = {
        "json": str(report_json.resolve()),
        "writtenAt": datetime.now(timezone.utc).isoformat(),
    }
    pointer.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return pointer


def _read_pointer(project_root: Path) -> Path | None:
    pointer = project_root / ".repolens" / _LAST_REPORT_NAME
    if not pointer.is_file():
        return None
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    raw = data.get("json") if isinstance(data, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _newest_gate_json(out_dir: Path) -> Path | None:
    if not out_dir.is_dir():
        return None
    candidates = sorted(
        out_dir.glob("gate_review_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_latest_report(
    project_root: Path,
    *,
    out_dir: Path | None = None,
) -> tuple[FindingReport, Path]:
    """Load FindingReport from last_report pointer or newest gate JSON."""
    path = _read_pointer(project_root)
    if path is None and out_dir is not None:
        path = _newest_gate_json(out_dir)
    if path is None:
        cfg = load_config(project_root)
        default_out = resolve_report_dir(project_root, cfg.general.report_dir)
        path = _newest_gate_json(default_out)
    if path is None or not path.is_file():
        raise FileNotFoundError(
            "No gate review JSON found. Run `repolens review` with "
            "`--format json` or `--format both` first."
        )
    report = FindingReport.model_validate_json(path.read_text(encoding="utf-8"))
    return report, path


def find_issue(report: FindingReport, uuid: str) -> Issue:
    """Prefer exact runId match; else first matching stableId."""
    key = uuid.strip()
    for issue in report.issues:
        if issue.runId and issue.runId.lower() == key.lower():
            return issue
    for issue in report.issues:
        if issue.stableId and issue.stableId.lower() == key.lower():
            return issue
    raise IssueNotFoundError(f"Issue UUID not found: {uuid}")


def _excerpt(project_root: Path, issue: Issue, *, max_chars: int = 2_000) -> str:
    path = project_root / issue.file
    if not path.is_file():
        return "(source file not found on disk)"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(could not read file: {exc})"
    lines = text.splitlines()
    idx = max(issue.line - 1, 0)
    start = max(idx - 8, 0)
    end = min(idx + 12, len(lines))
    chunk = "\n".join(lines[start:end])
    if len(chunk) > max_chars:
        chunk = chunk[:max_chars] + "\n…"
    return chunk


def _explain_prompt(issue: Issue, excerpt: str) -> str:
    return f"""You are RepoLens explain. Return ONLY valid JSON:
{{
  "problem": "string",
  "impact": "string",
  "solutions": [{{"title": "string", "tradeoffs": "string"}}],
  "diagramMermaid": "flowchart LR\\n  A --> B",
  "nextStep": "string"
}}
Provide 2–3 solutions with trade-offs.
Diagram: flowchart or sequenceDiagram only; keep it small.
Use British English.

Issue:
- title: {issue.title}
- severity: {issue.severity.value}
- category: {issue.category}
- file: {issue.file}:{issue.line}
- explanation: {issue.explanation}
- impact: {issue.impact}
- recommendedFix: {issue.recommendedFix}
- codeExample: {issue.codeExample}

Evidence excerpt:
```
{excerpt}
```
"""


def _parse_explain_doc(raw: str) -> ExplainDoc:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    data: Any = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("explain payload must be a JSON object")
    return ExplainDoc.model_validate(data)


def _degraded_doc(issue: Issue, *, error: str) -> ExplainDoc:
    return ExplainDoc(
        problem=issue.explanation or issue.title,
        impact=issue.impact or "(not provided)",
        solutions=[
            ExplainSolution(
                title="Apply recommended fix",
                tradeoffs=issue.recommendedFix or "See issue recommendedFix.",
            ),
            ExplainSolution(
                title="Add a regression test",
                tradeoffs="Extra effort; locks the fix in.",
            ),
        ],
        diagramMermaid="flowchart LR\n  Problem --> Impact --> Fix",
        nextStep=issue.recommendedFix or "Triage this finding in the next PR.",
    )


def render_explain_markdown(
    *,
    issue: Issue,
    doc: ExplainDoc,
    diagram_block: str,
    uuid: str,
) -> str:
    lines = [
        f"# Explain — {issue.title}",
        "",
        f"**UUID:** `{uuid}`  ",
        f"**File:** `{issue.file}:{issue.line}`  ",
        f"**Severity:** {issue.severity.value}  ",
        f"**Category:** {issue.category}",
        "",
        "## Problem",
        "",
        doc.problem.strip() or issue.explanation,
        "",
        "## Impact",
        "",
        (doc.impact or issue.impact or "_n/a_").strip(),
        "",
        "## Solutions",
        "",
    ]
    solutions = doc.solutions or []
    if not solutions:
        lines.append("_No solutions returned; see recommended fix on the issue._")
    for i, sol in enumerate(solutions, start=1):
        lines.append(f"{i}. **{sol.title}** — {sol.tradeoffs}".rstrip(" —"))
    lines.extend(["", "## Diagram", "", diagram_block, "", "## Recommended next step", ""])
    lines.append(doc.nextStep.strip() or issue.recommendedFix or "_n/a_")
    lines.append("")
    return "\n".join(lines)


def run_explain(
    *,
    uuid: str,
    project_root: Path,
    out_dir: Path | None = None,
    config: RepoLensConfig | None = None,
    diagram: bool = True,
    render_image: str | None = None,
    no_diagram: bool = False,
) -> Path:
    """Resolve issue, call LLM (or degrade), write ``explain_*.md``. Exit-path friendly."""
    root = project_root.resolve()
    cfg = config or load_config(root)
    if not cfg.explain.enabled:
        raise ExplainDisabledError(
            "Explain is disabled (`[explain] enabled = false`). "
            "Re-enable in config to deep-dive findings."
        )
    if not _UUID_RE.match(uuid.strip()):
        raise IssueNotFoundError(f"Invalid UUID: {uuid}")

    report_out = out_dir or resolve_report_dir(root, cfg.general.report_dir)
    report, _ = load_latest_report(root, out_dir=report_out)
    issue = find_issue(report, uuid)

    excerpt = _excerpt(root, issue)
    prompt = _explain_prompt(issue, excerpt)
    try:
        raw = analyze_raw(prompt, cfg.model)
        try:
            doc = _parse_explain_doc(raw)
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
            doc = _degraded_doc(issue, error="parse")
    except LlmError as exc:
        doc = _degraded_doc(issue, error=str(exc))

    want_diagram = (
        diagram
        and not no_diagram
        and (cfg.explain.diagram or "mermaid").lower() != "off"
    )
    render_mode = (render_image or cfg.explain.render_image or "auto").lower()
    if want_diagram:
        diag = process_diagram(
            doc.diagramMermaid or "flowchart LR\n  A --> B",
            render_image=render_mode,
            out_dir=report_out / "explain-assets",
        )
        if diag.kind == "mermaid" and diag.mermaid:
            diagram_block = f"```mermaid\n{diag.mermaid}\n```"
            if diag.notes:
                diagram_block += "\n\n_" + "; ".join(diag.notes) + "_"
            if diag.image_path:
                diagram_block += f"\n\n![diagram]({diag.image_path})"
        else:
            diagram_block = f"```\n{diag.textual or ''}\n```"
            if diag.notes:
                diagram_block += "\n\n_" + "; ".join(diag.notes) + "_"
    else:
        diagram_block = "_Diagram skipped._"

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    short = uuid.strip().split("-")[0]
    report_out.mkdir(parents=True, exist_ok=True)
    path = report_out / f"explain_{short}_{stamp}.md"
    path.write_text(
        render_explain_markdown(
            issue=issue, doc=doc, diagram_block=diagram_block, uuid=uuid.strip()
        ),
        encoding="utf-8",
    )
    return path
