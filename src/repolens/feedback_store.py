"""Local feedback event log → soft FP calibrations (Phase 6.7)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from repolens.config import DeepConfig
from repolens.schema import Issue, Severity
from repolens.triage import infer_issue_source

FEEDBACK_REL = Path(".repolens") / "feedback.jsonl"
_CALIB_TAG = "feedback_false_positive"
_CATEGORY_THRESHOLD = 2


def feedback_path(root: Path) -> Path:
    return root.resolve() / FEEDBACK_REL


def record_feedback(
    root: Path,
    *,
    stable_id: str,
    reason: str,
    category: str = "",
    file: str = "",
    title: str = "",
    note: str = "",
) -> Path:
    """Append one local feedback event (no upload)."""
    path = feedback_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "stableId": stable_id.strip(),
        "reason": reason.strip(),
        "category": category.strip(),
        "file": file.strip().replace("\\", "/"),
        "title": title.strip(),
        "note": note.strip(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def load_feedback_events(root: Path) -> list[dict]:
    path = feedback_path(root)
    if not path.is_file():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            events.append(row)
    return events


def _norm_file(path: str) -> str:
    return path.strip().replace("\\", "/").lower().lstrip("./")


def _demote_feedback(issue: Issue) -> Issue:
    if issue.severity not in {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}:
        return issue
    prefix = f"[calibrated: {_CALIB_TAG}]"
    explanation = issue.explanation
    if prefix not in explanation:
        explanation = f"{prefix} {explanation}"
    return issue.model_copy(
        update={"severity": Severity.LOW, "explanation": explanation}
    )


def apply_feedback_calibrations(
    issues: list[Issue],
    root: Path,
    deep: DeepConfig,
) -> list[Issue]:
    """Demote LLM/heuristic issues matching local false_positive feedback."""
    if deep.feedback_calibrations is False:
        return issues
    events = [
        e
        for e in load_feedback_events(root)
        if str(e.get("reason", "")).strip() == "false_positive"
    ]
    if not events:
        return issues

    file_cat: set[tuple[str, str]] = set()
    cat_counts: dict[str, int] = {}
    for e in events:
        cat = str(e.get("category") or "").strip().lower()
        file_ = _norm_file(str(e.get("file") or ""))
        if cat and file_:
            file_cat.add((file_, cat))
        if cat:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    hot_categories = {
        c for c, n in cat_counts.items() if n >= _CATEGORY_THRESHOLD
    }

    out: list[Issue] = []
    for issue in issues:
        if infer_issue_source(issue) == "scanner":
            out.append(issue)
            continue
        cat = (issue.category or "").strip().lower()
        file_ = _norm_file(issue.file or "")
        if (file_, cat) in file_cat or cat in hot_categories:
            out.append(_demote_feedback(issue))
        else:
            out.append(issue)
    return out


def lookup_issue_meta(root: Path, stable_id: str) -> dict[str, str]:
    """Best-effort category/file/title from last report pointer."""
    from repolens.explain import load_latest_report

    try:
        report, _path = load_latest_report(root)
    except (OSError, FileNotFoundError, ValueError):
        return {}
    key = stable_id.strip().lower()
    for issue in list(report.issues) + [r.issue for r in report.suppressedIssues]:
        if issue.stableId and issue.stableId.lower() == key:
            return {
                "category": issue.category or "",
                "file": issue.file or "",
                "title": issue.title or "",
            }
    return {}
