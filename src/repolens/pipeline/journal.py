"""Append-only review journal for interrupt / resume visibility."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def journal_path(root: Path) -> Path:
    return root / ".repolens" / "journal.jsonl"


def format_duration_ms(ms: int) -> str:
    """Human duration for CLI; JSONL keeps raw millisecond ints."""
    if ms < 1000:
        return "< 1s"
    total_seconds = ms / 1000.0
    if total_seconds < 60:
        text = f"{total_seconds:.1f}".rstrip("0").rstrip(".")
        return f"{text}s"
    minutes = int(total_seconds // 60)
    seconds = int(round(total_seconds - minutes * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}m {seconds}s"


def append_event(root: Path, event: str, **fields: Any) -> None:
    """Append one JSON object. Never raises into the review loop."""
    path = journal_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "event": event}
        body.update(fields)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, ensure_ascii=False) + "\n")
    except OSError:
        return


def summarize_chars(root: Path) -> dict[str, int]:
    """Honesty metrics from journal pass_completed rows (no Metis % invented)."""
    chars_in = 0
    chars_out = 0
    completed = 0
    resumed = 0
    for row in read_events(root):
        if row.get("event") != "pass_completed":
            continue
        completed += 1
        if row.get("resumed"):
            resumed += 1
        chars_in += int(row.get("chars_in") or 0)
        chars_out += int(row.get("chars_out") or 0)
    return {
        "pass_completed": completed,
        "resumed": resumed,
        "chars_in": chars_in,
        "chars_out": chars_out,
    }


def last_finished_label(root: Path) -> str | None:
    last: str | None = None
    for row in read_events(root):
        if row.get("event") == "pass_completed" and not row.get("degraded"):
            label = str(row.get("label") or row.get("role") or "").strip()
            if label:
                last = label
        if row.get("event") == "interrupted":
            fin = str(row.get("last_finished") or "").strip()
            if fin:
                last = fin
    return last


def read_events(root: Path) -> list[dict[str, Any]]:
    path = journal_path(root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict) and raw.get("event"):
            rows.append(raw)
    return rows
