"""Local feedback event log → soft FP calibrations (Phase 6.7 + #30 patterns)."""

from __future__ import annotations

import fnmatch
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from repolens.config import DeepConfig
from repolens.schema import Issue, Severity
from repolens.triage import infer_issue_source

FEEDBACK_REL = Path(".repolens") / "feedback.jsonl"
_CALIB_TAG = "feedback_false_positive"
_CATEGORY_THRESHOLD = 2
_TITLE_CLUSTER_THRESHOLD = 2
_PATH_PATTERN_THRESHOLD = 1  # one explicit/derived path pattern is enough

_TITLE_NOISE = re.compile(r"[^a-z0-9\s]+")
_WS = re.compile(r"\s+")


def feedback_path(root: Path) -> Path:
    return root.resolve() / FEEDBACK_REL


def normalize_title(title: str) -> str:
    """Cluster key for similar LLM titles (local-only; not cloud learning)."""
    text = title.strip().lower()
    text = _TITLE_NOISE.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    # Drop pure digit tokens so "line 12" / "line 40" still cluster.
    parts = [p for p in text.split() if not p.isdigit()]
    return " ".join(parts)


def derive_path_pattern(file: str) -> str | None:
    """Heuristic path glob from a dismissed file (e.g. ``scripts/dev_foo.py`` → ``scripts/dev_*``).

    Returns None when the pattern would be too broad (bare ``*.py`` in a shallow tree).
    """
    norm = _norm_file(file)
    if not norm or norm in {".", "/"}:
        return None
    path = Path(norm)
    parent = path.parent.as_posix()
    stem = path.stem
    if "_" in stem:
        prefix = stem.split("_", 1)[0]
        if len(prefix) >= 2:
            base = f"{prefix}_*"
            return f"{parent}/{base}{path.suffix}" if parent != "." else f"{base}{path.suffix}"
    # Same-directory wildcard is only used when the user passes --path-pattern.
    return None


def record_feedback(
    root: Path,
    *,
    stable_id: str,
    reason: str,
    category: str = "",
    file: str = "",
    title: str = "",
    note: str = "",
    path_pattern: str = "",
) -> Path:
    """Append one local feedback event (no upload)."""
    path = feedback_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_norm = file.strip().replace("\\", "/")
    pattern = path_pattern.strip().replace("\\", "/")
    if not pattern:
        pattern = derive_path_pattern(file_norm) or ""
    event = {
        "stableId": stable_id.strip(),
        "reason": reason.strip(),
        "category": category.strip(),
        "file": file_norm,
        "title": title.strip(),
        "titleNorm": normalize_title(title),
        "pathPattern": pattern,
        "note": note.strip(),
        "ts": datetime.now(UTC).isoformat(),
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


def _path_matches(file: str, pattern: str) -> bool:
    if not pattern:
        return False
    cand = _norm_file(file)
    pat = pattern.strip().replace("\\", "/").lower().lstrip("./")
    return fnmatch.fnmatchcase(cand, pat)


def _demote_feedback(issue: Issue, *, provenance: str) -> Issue:
    if issue.severity not in {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}:
        return issue
    prefix = f"[calibrated: {_CALIB_TAG}; {provenance}]"
    explanation = issue.explanation
    # Avoid stacking duplicate tags on re-runs.
    if f"[calibrated: {_CALIB_TAG}" in explanation:
        return issue.model_copy(update={"severity": Severity.LOW})
    explanation = f"{prefix} {explanation}"
    return issue.model_copy(
        update={"severity": Severity.LOW, "explanation": explanation}
    )


def _index_false_positives(
    events: list[dict],
) -> tuple[
    set[tuple[str, str]],
    set[str],
    set[tuple[str, str]],
    set[tuple[str, str]],
]:
    file_cat: set[tuple[str, str]] = set()
    cat_counts: dict[str, int] = {}
    path_pat_counts: dict[tuple[str, str], int] = {}
    title_counts: dict[tuple[str, str], int] = {}

    for event in events:
        cat = str(event.get("category") or "").strip().lower()
        file_ = _norm_file(str(event.get("file") or ""))
        title_n = str(
            event.get("titleNorm") or normalize_title(str(event.get("title") or ""))
        )
        pattern = str(event.get("pathPattern") or "").strip()
        if not pattern and file_:
            pattern = derive_path_pattern(file_) or ""
        if cat and file_:
            file_cat.add((file_, cat))
        if cat:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if cat and pattern:
            key = (cat, pattern.lower().lstrip("./"))
            path_pat_counts[key] = path_pat_counts.get(key, 0) + 1
        if cat and title_n:
            title_counts[(cat, title_n)] = title_counts.get((cat, title_n), 0) + 1

    hot_categories = {c for c, n in cat_counts.items() if n >= _CATEGORY_THRESHOLD}
    hot_path_patterns = {
        k for k, n in path_pat_counts.items() if n >= _PATH_PATTERN_THRESHOLD
    }
    hot_titles = {k for k, n in title_counts.items() if n >= _TITLE_CLUSTER_THRESHOLD}
    return file_cat, hot_categories, hot_path_patterns, hot_titles


def _calibrated_issue(
    issue: Issue,
    *,
    file_cat: set[tuple[str, str]],
    hot_categories: set[str],
    hot_path_patterns: set[tuple[str, str]],
    hot_titles: set[tuple[str, str]],
) -> Issue:
    """First matching rule wins. Scanner issues are left unchanged."""
    if infer_issue_source(issue) == "scanner":
        return issue
    cat = (issue.category or "").strip().lower()
    file_ = _norm_file(issue.file or "")
    title_n = normalize_title(issue.title or "")
    if (file_, cat) in file_cat:
        return _demote_feedback(issue, provenance="file+category")
    for pcat, pattern in hot_path_patterns:
        if pcat == cat and _path_matches(file_, pattern):
            return _demote_feedback(issue, provenance=f"path_pattern:{pattern}")
    if (cat, title_n) in hot_titles:
        return _demote_feedback(issue, provenance="title_cluster")
    if cat in hot_categories:
        return _demote_feedback(issue, provenance="category_cluster")
    return issue


def apply_feedback_calibrations(
    issues: list[Issue],
    root: Path,
    deep: DeepConfig,
) -> list[Issue]:
    """Demote LLM/heuristic issues matching local false_positive feedback.

    Match order (first hit wins provenance string):
    1. Exact ``file`` + ``category``
    2. ``category`` + ``pathPattern`` (fnmatch) — #30
    3. Hot ``category`` + normalised ``title`` (≥2) — #30
    4. Hot ``category`` (≥2 dismissals)
    """
    if deep.feedback_calibrations is False:
        return issues
    events = [
        event
        for event in load_feedback_events(root)
        if str(event.get("reason", "")).strip() == "false_positive"
    ]
    if not events:
        return issues
    file_cat, hot_categories, hot_path_patterns, hot_titles = _index_false_positives(
        events
    )
    return [
        _calibrated_issue(
            issue,
            file_cat=file_cat,
            hot_categories=hot_categories,
            hot_path_patterns=hot_path_patterns,
            hot_titles=hot_titles,
        )
        for issue in issues
    ]


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
