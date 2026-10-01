"""Learned local preferences from feedback.jsonl (skip globs + hotspot boosts)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from repolens.feedback_store import derive_path_pattern, load_feedback_events

PREFS_REL = Path(".repolens") / "learned_prefs.json"
_MIN_PATTERN_HITS = 2


@dataclass
class LearnedPrefs:
    skip_globs: list[str] = field(default_factory=list)
    hotspot_globs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def prefs_path(root: Path) -> Path:
    return root.resolve() / PREFS_REL


def load_learned_prefs(root: Path) -> LearnedPrefs:
    path = prefs_path(root)
    if not path.is_file():
        return LearnedPrefs()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LearnedPrefs()
    if not isinstance(raw, dict):
        return LearnedPrefs()
    return LearnedPrefs(
        skip_globs=[str(x) for x in raw.get("skip_globs", []) if str(x).strip()],
        hotspot_globs=[str(x) for x in raw.get("hotspot_globs", []) if str(x).strip()],
        notes=[str(x) for x in raw.get("notes", []) if str(x).strip()],
    )


def save_learned_prefs(root: Path, prefs: LearnedPrefs) -> Path:
    path = prefs_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(prefs), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def derive_learned_prefs(root: Path) -> LearnedPrefs:
    """Aggregate false-positive path patterns into skip globs (≥2 hits)."""
    events = load_feedback_events(root)
    patterns: Counter[str] = Counter()
    for event in events:
        if str(event.get("reason", "")).lower() not in {
            "false_positive",
            "fp",
            "not_applicable",
            "wont_fix",
        } and "false" not in str(event.get("reason", "")).lower():
            # Still count explicit pathPattern from feedback down.
            pass
        pattern = str(event.get("pathPattern") or "").strip().replace("\\", "/")
        if not pattern:
            pattern = derive_path_pattern(str(event.get("file") or "")) or ""
        if pattern:
            patterns[pattern] += 1
    skip = sorted(p for p, n in patterns.items() if n >= _MIN_PATTERN_HITS)
    notes = []
    if skip:
        notes.append(
            f"Derived {len(skip)} skip glob(s) from feedback patterns "
            f"(threshold ≥{_MIN_PATTERN_HITS})"
        )
    else:
        notes.append("No repeated path patterns yet — need more feedback downs")
    return LearnedPrefs(skip_globs=skip, hotspot_globs=[], notes=notes)


def merge_skip_globs(configured: list[str], learned: LearnedPrefs) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in [*configured, *learned.skip_globs]:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
