"""Finding suppressions: ``.repolens-ignore`` + inline disable comments (Phase 6.7)."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from repolens.schema import Issue, SuppressedIssue
from repolens.triage import infer_issue_source

IGNORE_FILENAME = ".repolens-ignore"

_VALID_REASONS = frozenset(
    {"false_positive", "wont_fix", "accepted_risk", "other"}
)

_DISABLE_NEXT = re.compile(
    r"(?:#|//)\s*repolens:disable-next-line(?:\s+(\S+))?\s*$",
    re.IGNORECASE,
)
_DISABLE = re.compile(
    r"(?:#|//)\s*repolens:disable(?:\s+(\S+))?\s*$",
    re.IGNORECASE,
)
_ENABLE = re.compile(
    r"(?:#|//)\s*repolens:enable\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IgnoreEntry:
    reason: str
    stable_id: str | None = None
    file: str | None = None
    category: str | None = None
    note: str = ""
    expires: date | None = None

    def active_on(self, today: date | None = None) -> bool:
        if self.expires is None:
            return True
        return (today or date.today()) <= self.expires


def _norm_file(path: str) -> str:
    return path.strip().replace("\\", "/").lower().lstrip("./")


def load_ignore_file(root: Path) -> list[IgnoreEntry]:
    """Load ``.repolens-ignore`` from project root. Missing file → empty."""
    path = root / IGNORE_FILENAME
    if not path.is_file():
        return []
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("ignore") or []
    if not isinstance(rows, list):
        raise ValueError(f"{IGNORE_FILENAME}: [[ignore]] must be an array of tables")
    out: list[IgnoreEntry] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{IGNORE_FILENAME}: ignore[{i}] must be a table")
        reason = str(row.get("reason") or "").strip()
        if not reason:
            raise ValueError(
                f"{IGNORE_FILENAME}: ignore[{i}] requires reason "
                f"(false_positive|wont_fix|accepted_risk|other)"
            )
        if reason not in _VALID_REASONS:
            raise ValueError(
                f"{IGNORE_FILENAME}: ignore[{i}] unknown reason {reason!r}; "
                f"use one of {sorted(_VALID_REASONS)}"
            )
        sid = row.get("stableId") or row.get("stable_id")
        file_ = row.get("file")
        category = row.get("category")
        if not sid and not (file_ and category):
            raise ValueError(
                f"{IGNORE_FILENAME}: ignore[{i}] needs stableId or file+category"
            )
        expires = _parse_expires(row.get("expires"), index=i)
        out.append(
            IgnoreEntry(
                reason=reason,
                stable_id=str(sid).strip() if sid else None,
                file=str(file_).strip() if file_ else None,
                category=str(category).strip() if category else None,
                note=str(row.get("note") or "").strip(),
                expires=expires,
            )
        )
    return out


def _parse_expires(value: object, *, index: int) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(
            f"{IGNORE_FILENAME}: ignore[{index}] invalid expires {value!r}"
        ) from exc


def parse_disable_lines(text: str) -> set[int]:
    """Return 1-based line numbers covered by disable comments in ``text``."""
    lines = text.splitlines()
    covered: set[int] = set()
    in_block = False
    block_category: str | None = None
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if _ENABLE.match(stripped):
            in_block = False
            block_category = None
            continue
        m_block = _DISABLE.match(stripped)
        if m_block and "disable-next-line" not in stripped.lower():
            in_block = True
            block_category = m_block.group(1)
            continue
        m_next = _DISABLE_NEXT.match(stripped)
        if m_next:
            # Mark next physical line (if any)
            if idx < len(lines):
                covered.add(idx + 1)
            continue
        if in_block:
            covered.add(idx)
            _ = block_category  # reserved for optional category filter later
    return covered


def _safe_project_file(root: Path, relative: str) -> Path | None:
    """Resolve ``relative`` under ``root``; reject path escape."""
    rel = relative.replace("\\", "/").lstrip("./")
    if not rel or ".." in Path(rel).parts:
        return None
    root_res = root.resolve()
    candidate = (root_res / rel).resolve()
    try:
        candidate.relative_to(root_res)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _disable_covers(root: Path, issue: Issue) -> bool:
    """True when an inline disable covers this issue line (llm/heuristic only)."""
    src = infer_issue_source(issue)
    if src == "scanner":
        return False
    path = _safe_project_file(root, issue.file)
    if path is None:
        path = _safe_project_file(root, _norm_file(issue.file))
    if path is None:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return issue.line in parse_disable_lines(text)


def _ignore_match(entry: IgnoreEntry, issue: Issue) -> bool:
    if not entry.active_on():
        return False
    if entry.stable_id and issue.stableId:
        if entry.stable_id.lower() == issue.stableId.lower():
            return True
    if entry.file and entry.category:
        if (
            _norm_file(entry.file) == _norm_file(issue.file)
            and entry.category.strip().lower() == issue.category.strip().lower()
        ):
            return True
    return False


def apply_suppressions(
    root: Path,
    issues: list[Issue],
) -> tuple[list[Issue], list[SuppressedIssue]]:
    """Split issues into active vs suppressed (ignore file + disable comments)."""
    entries = load_ignore_file(root)
    active: list[Issue] = []
    suppressed: list[SuppressedIssue] = []
    for issue in issues:
        matched_entry: IgnoreEntry | None = None
        for entry in entries:
            if _ignore_match(entry, issue):
                matched_entry = entry
                break
        if matched_entry is not None:
            suppressed.append(
                SuppressedIssue(
                    issue=issue,
                    reason=matched_entry.reason,
                    mechanism="ignore_file",
                    note=matched_entry.note,
                )
            )
            continue
        if _disable_covers(root, issue):
            suppressed.append(
                SuppressedIssue(
                    issue=issue,
                    reason="other",
                    mechanism="disable_comment",
                    note="inline repolens:disable",
                )
            )
            continue
        active.append(issue)
    return active, suppressed


def append_ignore_entry(
    root: Path,
    *,
    stable_id: str | None = None,
    file: str | None = None,
    category: str | None = None,
    reason: str,
    note: str = "",
    expires: str | None = None,
) -> Path:
    """Append one ``[[ignore]]`` table to ``.repolens-ignore`` (create if needed)."""
    if reason not in _VALID_REASONS:
        raise ValueError(f"unknown reason {reason!r}; use one of {sorted(_VALID_REASONS)}")
    if not stable_id and not (file and category):
        raise ValueError("need stable_id or file+category")
    path = root / IGNORE_FILENAME
    lines = [
        "",
        "[[ignore]]",
    ]
    def _toml_str(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    if stable_id:
        lines.append(f"stableId = {_toml_str(stable_id)}")
    if file:
        lines.append(f"file = {_toml_str(file)}")
    if category:
        lines.append(f"category = {_toml_str(category)}")
    lines.append(f"reason = {_toml_str(reason)}")
    if note:
        lines.append(f"note = {_toml_str(note)}")
    if expires:
        lines.append(f"expires = {_toml_str(expires)}")
    lines.append(f"# added {datetime.now(timezone.utc).date().isoformat()} UTC")
    lines.append("")
    existing = path.read_text(encoding="utf-8") if path.is_file() else "# RepoLens suppressions\n"
    path.write_text(existing.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")
    # Validate round-trip
    load_ignore_file(root)
    return path
