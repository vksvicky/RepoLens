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


def postmortem_data(root: Path) -> dict[str, Any]:
    """Structured post-mortem with raw millisecond ints (machine-safe)."""
    events = read_events(root)
    started = next((e for e in events if e.get("event") == "review_started"), None)
    interrupted = next(
        (e for e in reversed(events) if e.get("event") == "interrupted"), None
    )
    verify = next(
        (e for e in reversed(events) if e.get("event") == "verify_completed"), None
    )
    completed = [e for e in events if e.get("event") == "pass_completed"]
    started_passes = [e for e in events if e.get("event") == "pass_started"]
    unfinished: str | None = None
    if interrupted is not None:
        finished_labels = {
            str(e.get("label") or e.get("role") or "") for e in completed
        }
        for row in reversed(started_passes):
            label = str(row.get("label") or row.get("role") or "").strip()
            if label and label not in finished_labels:
                unfinished = label
                break
        status = (
            f"INTERRUPTED during {unfinished}"
            if unfinished
            else "INTERRUPTED"
        )
    else:
        status = "COMPLETED"
    return {
        "run_id": (started or {}).get("run_id"),
        "role_packs": (started or {}).get("role_packs"),
        "status": status,
        "interrupted_during": unfinished,
        "completed_passes": completed,
        "verify": verify,
        "last_finished": last_finished_label(root),
        "chars": summarize_chars(root),
        "events": len(events),
    }


def build_postmortem(root: Path) -> str:
    """Human-readable journal post-mortem (formatted durations only here)."""
    data = postmortem_data(root)
    if data["events"] == 0:
        return f"No journal at {journal_path(root)}"
    lines = [
        f"Run ID: {data['run_id'] or '(unknown)'}",
        f"Status: {data['status']}",
        f"role_packs: {'on' if data.get('role_packs') else 'off'}",
        "Completed passes:",
    ]
    for row in data["completed_passes"]:
        label = str(row.get("label") or row.get("role") or "pass")
        files = row.get("files_count")
        pack = row.get("pack_mode") or "full"
        findings = row.get("findings_count", 0)
        dur = format_duration_ms(int(row.get("pass_duration_ms") or 0))
        wait = format_duration_ms(int(row.get("queue_wait_ms") or 0))
        file_bit = f"{files} files ({pack}), " if files is not None else ""
        lines.append(
            f"  ✓ {label}: {file_bit}{findings} findings, {dur} "
            f"(queue wait: {wait})"
        )
    during = data.get("interrupted_during")
    if during:
        lines.append(f"  — {during}: started, not completed")
    verify = data.get("verify")
    if verify:
        lines.append(
            f"Verify: {verify.get('grounded_count', 0)} grounded, "
            f"{verify.get('suspect_count', 0)} suspect"
        )
    else:
        lines.append("Verify: (not run)")
    last = data.get("last_finished")
    if last:
        lines.append(f"Last finished: {last}")
    lines.append(
        f"Resume: repolens review --resume --path {root} "
        "(re-run one pass: --retry-pass p3)"
    )
    chars = data["chars"]
    lines.append(
        f"Honesty: chars_in={chars['chars_in']:,} chars_out={chars['chars_out']:,} "
        "(not a Metis % claim)"
    )
    return "\n".join(lines)
