"""Per-issue explain deep-dives (Phase 6)."""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from repolens.config import RepoLensConfig, load_config, resolve_report_dir
from repolens.explain_prompt import (
    ExplainDoc,
    ExplainSolution,
    _call_explain_llm,
    _evidence_bundle,
    _safe_issue_path,
    _write_explain_markdown,
    dedupe_solutions,
)
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
from repolens.llm import default_model, resolve_llm_timeout
from repolens.progress import ReviewProgress, null_progress
from repolens.schema import FindingReport, Issue

_LAST_REPORT_NAME = "last_report.json"
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class ExplainDisabledError(RuntimeError):
    """Raised when ``[explain].enabled`` is false."""


class IssueNotFoundError(LookupError):
    """Raised when no issue matches the given UUID."""


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

    provider = cfg.model.provider or "unknown"
    model_name = cfg.model.model or default_model(cfg.model.provider)
    timeout = resolve_llm_timeout(cfg.model)
    started = time.monotonic()
    doc = _call_explain_llm(
        issue=issue,
        outline=outline,
        excerpt=excerpt,
        cfg=cfg,
        prog=prog,
        provider=provider,
        model_name=model_name,
        timeout=timeout,
    )
    duration = time.monotonic() - started
    return _write_explain_markdown(
        issue=issue,
        doc=doc,
        uuid=uuid,
        outline=outline,
        provider=provider,
        model_name=model_name,
        duration=duration,
        report_out=report_out,
        diagram=diagram,
        no_diagram=no_diagram,
        render_image=render_image,
        cfg=cfg,
        prog=prog,
    )


# Re-export types/helpers used by tests and callers via ``repolens.explain``.
__all__ = [
    "ExplainDisabledError",
    "ExplainDoc",
    "ExplainSolution",
    "IssueNotFoundError",
    "_degraded_doc",
    "_evidence_bundle",
    "_process_diagram_block",
    "_safe_issue_path",
    "build_diagram_from_moves",
    "build_recommended_next_step",
    "dedupe_solutions",
    "find_issue",
    "import_diff_risk_notes",
    "load_latest_report",
    "next_step_is_vague",
    "parse_move",
    "render_explain_markdown",
    "run_explain",
    "sanitize_explain_mermaid",
    "write_last_report_pointer",
]
