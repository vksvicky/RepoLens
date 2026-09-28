"""Per-issue explain deep-dives (Phase 6)."""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from repolens.config import RepoLensConfig, load_config, resolve_report_dir
from repolens.explain_render import (
    _degraded_doc,
    _process_diagram_block,
    render_explain_markdown,
)
from repolens.explain_render import (
    build_diagram_from_moves as build_diagram_from_moves,
)
from repolens.explain_render import (
    build_recommended_next_step as build_recommended_next_step,
)
from repolens.explain_render import (
    import_diff_risk_notes as import_diff_risk_notes,
)
from repolens.explain_render import (
    next_step_is_vague as next_step_is_vague,
)
from repolens.explain_render import parse_move as parse_move
from repolens.explain_render import (
    sanitize_explain_mermaid as sanitize_explain_mermaid,
)
from repolens.file_outline import format_file_outline
from repolens.llm import LlmError, analyze_raw, default_model, resolve_llm_timeout
from repolens.progress import LlmGenerateProgress, ReviewProgress, null_progress
from repolens.schema import FindingReport, Issue

_LAST_REPORT_NAME = "last_report.json"
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_GENERIC_MODULE_RE = re.compile(
    r"\b(types?_module|ui_module|io_module|localization_module|"
    r"utils?_module|helpers?_module|common_module)\b",
    re.IGNORECASE,
)


class ExplainDisabledError(RuntimeError):
    """Raised when ``[explain].enabled`` is false."""


class IssueNotFoundError(LookupError):
    """Raised when no issue matches the given UUID."""


class ExplainSolution(BaseModel):
    title: str
    tradeoffs: str = ""
    impactEffort: str = ""
    moves: list[str] = Field(default_factory=list)
    importDiff: str = ""


class ExplainDoc(BaseModel):
    problem: str
    impact: str = ""
    solutions: list[ExplainSolution] = Field(default_factory=list)
    proposedRefactorDiff: str = ""
    diagramMermaid: str = ""
    nextStep: str = ""


def write_last_report_pointer(project_root: Path, report_json: Path) -> Path:
    """Record the latest JSON report path under ``.repolens/``."""
    meta_dir = project_root / ".repolens"
    meta_dir.mkdir(parents=True, exist_ok=True)
    pointer = meta_dir / _LAST_REPORT_NAME
    payload = {
        "json": str(report_json.resolve()),
        "writtenAt": datetime.now(UTC).isoformat(),
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
        (
            p
            for p in out_dir.glob("gate_review_report_*.json")
            if not p.name.endswith(".sarif.json")
        ),
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
    root = project_root.resolve()
    searched: list[str] = [f".repolens/{_LAST_REPORT_NAME} under {root}"]
    path = _read_pointer(root)
    if path is None and out_dir is not None:
        out = out_dir if out_dir.is_absolute() else (root / out_dir)
        searched.append(str(out.resolve()))
        path = _newest_gate_json(out)
    if path is None:
        cfg = load_config(root)
        default_out = resolve_report_dir(root, cfg.general.report_dir)
        searched.append(str(default_out.resolve()))
        path = _newest_gate_json(default_out)
    if path is None or not path.is_file():
        looked = "; ".join(searched)
        raise FileNotFoundError(
            "No gate review JSON found. Run `repolens review` with "
            "`--format json` or `--format both` first "
            f"(looked in: {looked}). "
            "If the report is in another repo, pass that root as `--path` "
            "and its reports dir as `--out`."
        )
    report = FindingReport.model_validate_json(path.read_text(encoding="utf-8"))
    return report, path


def find_issue(report: FindingReport, uuid: str) -> Issue:
    """Prefer exact Occurrence (runId) match; else first matching Fingerprint."""
    key = uuid.strip()
    for issue in report.issues:
        if issue.runId and issue.runId.lower() == key.lower():
            return issue
    for issue in report.issues:
        if issue.stableId and issue.stableId.lower() == key.lower():
            return issue
    raise IssueNotFoundError(f"Issue UUID not found: {uuid}")


def _safe_issue_path(project_root: Path, issue_file: str) -> Path | None:
    """Resolve ``issue.file`` only when it stays under the project root."""
    root = project_root.resolve()
    raw = (issue_file or "").strip()
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", raw):
        return None
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _excerpt(project_root: Path, issue: Issue, *, max_chars: int = 2_000) -> str:
    path = _safe_issue_path(project_root, issue.file)
    if path is None or not path.is_file():
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


def _evidence_bundle(project_root: Path, issue: Issue) -> tuple[str, str]:
    """Return (outline_or_empty, line_excerpt) for the prompt."""
    path = _safe_issue_path(project_root, issue.file)
    outline = ""
    if path is not None and path.is_file():
        # Mega-file and other large findings: structure first.
        want_outline = (
            (issue.category or "").startswith("heuristic.mega_file")
            or (issue.category or "").startswith("arch.readability")
        )
        outline = format_file_outline(
            path,
            min_lines_for_outline=1 if want_outline else 80,
            display_path=issue.file.replace("\\", "/"),
        )
    excerpt = _excerpt(project_root, issue)
    return outline, excerpt


def _explain_prompt(issue: Issue, *, outline: str, excerpt: str) -> str:
    outline_block = outline.strip() or "(no structure outline available)"
    next_step_hint = (
        "ordered checklist: first extract WHICH symbol into WHICH file, "
        "then imports, then verify — never a vague one-liner"
    )
    return f"""You are RepoLens explain — a senior engineer writing an *actionable*
refactor / fix brief for ONE finding. Return ONLY valid JSON:
{{
  "problem": "string — specific to THIS file; must NOT merely repeat the title",
  "impact": "string — concrete developer / product risk",
  "solutions": [
    {{
      "title": "string — name a real split or fix",
      "tradeoffs": "string",
      "impactEffort": "e.g. High impact, low effort",
      "moves": [
        "existing_symbol (lines A–B) → suggested_new_module.py"
      ],
      "importDiff": "unified diff snippet showing import / call-site updates"
    }}
  ],
  "proposedRefactorDiff": "optional larger unified diff (imports + stubs)",
  "diagramMermaid": "flowchart TD …",
  "nextStep": "{next_step_hint}"
}}

Hard rules (violations make the answer useless):
1. You MUST ground every suggestion in the structure outline and/or excerpt.
2. You MUST ONLY suggest new module/file names derived from *existing*
   class/function names in the outline. DO NOT invent generic names like
   types_module, UI_module, IO_module, localization_module, utils_module,
   or fake suffixes like _ui.py / _logic.py unless those words appear in
   the real symbol names.
3. If you recommend splitting a file, each `moves` entry must name a real
   existing symbol and where it should go.
4. Provide **1 to 3 distinct** solutions. Do **not** invent filler options
   when there is only one clear path. Do **not** repeat the same `moves`
   under different titles. Prefer one excellent plan over three clones.
5. Import / refactor diffs (critical):
   - Prefer **additive** diffs: add new `from … import …` lines.
   - Do **NOT** delete standard-library or third-party imports the file
     still needs (e.g. `typer`, `pathlib`, `httpx`, framework decorators).
   - Do **NOT** wipe the whole import block and replace it with only the
     new local modules — that breaks the remaining code.
   - If commands stay registered in the original file, keep `typer` /
     decorator imports there; show extracting *bodies* into new modules
     and thin wrappers / re-exports, not deleting registration imports.
6. Diagrams: flowchart TD or LR with **bare ids only** and tight
   undirected edges (no spaces, no ``>``): ``commands_review---run_mode``.
   Never ``-->`` (IDE Markdown previews eat the ``>``). Never ``file.py``
   tokens, never ``id[label]`` / ``id(label)`` / quoted labels. Put human
   names in Markdown prose, not in Mermaid. Never placeholder ModuleA/ModuleB.
7. ``nextStep`` must be an ordered checklist naming real symbols and target
   files from ``moves`` (e.g. "1. Extract `_run_mode` → `run_mode.py`.
   2. … 3. Additive imports in host; keep typer. 4. Re-run tests.").
   Forbidden: vague lines like "Refactor file.py into separate modules".
8. British English. No markdown fences around the JSON.

Issue:
- title: {issue.title}
- severity: {issue.severity.value}
- category: {issue.category}
- file: {issue.file}:{issue.line}
- explanation: {issue.explanation}
- impact: {issue.impact}
- recommendedFix: {issue.recommendedFix}
- codeExample: {issue.codeExample}

Structure outline (authoritative — prefer this over guessing):
{outline_block}

Local excerpt around reported line (may be weak for mega-files; trust outline):
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


def _looks_generic_boilerplate(doc: ExplainDoc) -> bool:
    blob = " ".join(
        [
            doc.problem,
            doc.diagramMermaid,
            doc.proposedRefactorDiff,
            *(s.title for s in doc.solutions),
            *(s.importDiff for s in doc.solutions),
            *(" ".join(s.moves) for s in doc.solutions),
        ]
    )
    if _GENERIC_MODULE_RE.search(blob):
        return True
    # Classic empty mega-file waffle
    titles = " ".join(s.title.lower() for s in doc.solutions)
    if (
        "split by responsibility" in titles
        and "modularize" in titles
        and not any(s.moves for s in doc.solutions)
    ):
        return True
    return False


def _solution_fingerprint(sol: ExplainSolution) -> str:
    moves = tuple(m.strip().lower() for m in sol.moves)
    if moves:
        return "moves:" + "|".join(moves)
    return "title:" + sol.title.strip().lower()


def dedupe_solutions(solutions: list[ExplainSolution]) -> list[ExplainSolution]:
    """Drop near-duplicate plans (same moves under different titles)."""
    seen: set[str] = set()
    out: list[ExplainSolution] = []
    for sol in solutions:
        key = _solution_fingerprint(sol)
        if key in seen:
            continue
        seen.add(key)
        out.append(sol)
    return out


def run_explain(
    *,
    uuid: str,
    project_root: Path,
    out_dir: Path | None = None,
    config: RepoLensConfig | None = None,
    diagram: bool = True,
    render_image: str | None = None,
    no_diagram: bool = False,
    progress: ReviewProgress | None = None,
) -> Path:
    """Resolve issue, call LLM (or degrade), write ``explain_*.md``."""
    root = project_root.resolve()
    cfg = config or load_config(root)
    prog = progress or null_progress()
    if not cfg.explain.enabled:
        raise ExplainDisabledError(
            "Explain is disabled (`[explain] enabled = false`). "
            "Re-enable in config to deep-dive findings."
        )
    if not _UUID_RE.match(uuid.strip()):
        raise IssueNotFoundError(f"Invalid UUID: {uuid}")

    report_out = out_dir or resolve_report_dir(root, cfg.general.report_dir)
    if report_out is not None and not report_out.is_absolute():
        report_out = root / report_out

    prog.phase("Explain: loading latest gate report…")
    report, report_path = load_latest_report(root, out_dir=report_out)
    prog.detail(f"report: {report_path}")
    issue = find_issue(report, uuid)
    prog.phase(
        f"Explain: found {issue.severity.value} · {issue.category} · `{issue.file}`"
    )

    outline, excerpt = _evidence_bundle(root, issue)
    if outline:
        prog.detail(
            f"structure outline: {outline.count(chr(10)) + 1} line(s) of symbols"
        )
    else:
        prog.detail("structure outline: none (small file or unsupported language)")

    prompt = _explain_prompt(issue, outline=outline, excerpt=excerpt)
    provider = cfg.model.provider or "unknown"
    model_name = cfg.model.model or default_model(cfg.model.provider)
    timeout = resolve_llm_timeout(cfg.model)
    started = time.monotonic()
    doc: ExplainDoc
    try:
        gen = LlmGenerateProgress()
        ollama_base = cfg.model.base_url if provider == "ollama" else None

        def status_fn(
            progress: LlmGenerateProgress = gen,
            base: str | None = ollama_base,
            use_ollama: bool = provider == "ollama",
        ) -> str | None:
            bits = [progress.summary()]
            if use_ollama:
                from repolens.provider_status import ollama_running_summary

                live = ollama_running_summary(base)
                if live:
                    bits.append(live)
            return " | ".join(bits)

        wait_label = (
            f"Explain LLM — {model_name} via {provider} "
            f"(timeout {timeout:g}s)"
        )
        with prog.waiting(
            wait_label,
            hint=f"prompt ≈ {len(prompt):,} chars",
            status_fn=status_fn,
        ):
            raw = analyze_raw(prompt, cfg.model, on_delta=gen.note_delta)
        gen.mark_done()
        try:
            doc = _parse_explain_doc(raw)
            before = len(doc.solutions)
            doc.solutions = dedupe_solutions(doc.solutions)
            if len(doc.solutions) < before:
                prog.detail(
                    f"dropped {before - len(doc.solutions)} duplicate solution(s)"
                )
            if _looks_generic_boilerplate(doc):
                prog.detail(
                    "LLM answer looked like generic boilerplate — "
                    "falling back to outline-guided degraded explain"
                )
                doc = _degraded_doc(
                    issue, error="generic_boilerplate", outline=outline
                )
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
            doc = _degraded_doc(issue, error="parse", outline=outline)
    except LlmError as exc:
        doc = _degraded_doc(issue, error=str(exc), outline=outline)
    duration = time.monotonic() - started

    want_diagram = (
        diagram
        and not no_diagram
        and (cfg.explain.diagram or "mermaid").lower() != "off"
    )
    render_mode = (render_image or cfg.explain.render_image or "auto").lower()
    if want_diagram:
        prog.phase("Explain: processing diagram…")
    diagram_block = _process_diagram_block(want_diagram, render_mode, doc, report_out)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    short = uuid.strip().split("-")[0]
    report_out.mkdir(parents=True, exist_ok=True)
    path = report_out / f"explain_{short}_{stamp}.md"
    prog.phase(f"Explain: writing {path.name}…")
    path.write_text(
        render_explain_markdown(
            issue=issue,
            doc=doc,
            diagram_block=diagram_block,
            uuid=uuid.strip(),
            outline=outline,
            provider=provider,
            model=model_name,
            duration_seconds=duration,
        ),
        encoding="utf-8",
    )
    prog.phase("Explain: done")
    return path
