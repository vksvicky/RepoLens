"""``repolens review --preset pr|changed|release`` flag bundles.

A preset only fills flags the user left at their CLI default; any explicit flag
(``--timeout``, ``--no-deep``, ``--git-diff``, ``--ci`` ...) wins. ``pr`` wraps
the existing ``--scanners-only`` path, so it never calls an LLM or needs Ollama.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, cast

PresetName = Literal["pr", "changed", "release"]
PRESET_NAMES: tuple[str, ...] = ("pr", "changed", "release")

CHANGED_TIMEOUT_S = 900.0
RELEASE_TIMEOUT_S = 3600.0

PRESET_HELP = (
    "pr (scanners only, no LLM/Ollama) | changed (--git-diff auto --deep) | "
    "release (--full --full-audit --deep, long timeout). "
    "Explicit flags override the preset."
)


@dataclass(frozen=True)
class ReviewFlagBag:
    """The review flags a preset may set; defaults mirror the CLI defaults."""

    scanners_only: bool = False
    ci: bool = False
    dry_run: bool = False
    deep: bool | None = None
    git_diff: str | None = None
    force_full: bool = False
    force_changed: bool = False
    full_audit: bool = False
    timeout: float | None = None


def parse_preset(value: str | None) -> PresetName | None:
    """Normalise a ``--preset`` value; raise ``ValueError`` on unknown names."""
    if value is None:
        return None
    name = value.strip().lower()
    if name not in PRESET_NAMES:
        raise ValueError(f"--preset must be {' | '.join(PRESET_NAMES)}")
    return cast(PresetName, name)


def _has_scope(args: ReviewFlagBag) -> bool:
    return bool(args.git_diff is not None or args.force_full or args.force_changed)


def _pr(args: ReviewFlagBag) -> ReviewFlagBag:
    # --ci / --dry-run are explicit user intents that conflict with scanners-only.
    skip = args.ci or args.dry_run
    return replace(
        args,
        scanners_only=args.scanners_only or not skip,
        deep=args.deep if args.deep is not None else False,
    )


def _changed(args: ReviewFlagBag) -> ReviewFlagBag:
    return replace(
        args,
        git_diff=args.git_diff if _has_scope(args) else "auto",
        deep=args.deep if args.deep is not None else True,
        timeout=args.timeout if args.timeout is not None else CHANGED_TIMEOUT_S,
    )


def _release(args: ReviewFlagBag) -> ReviewFlagBag:
    return replace(
        args,
        force_full=args.force_full or not _has_scope(args),
        full_audit=True,
        deep=args.deep if args.deep is not None else True,
        timeout=args.timeout if args.timeout is not None else RELEASE_TIMEOUT_S,
    )


_APPLIERS = {"pr": _pr, "changed": _changed, "release": _release}


def apply_preset(preset: PresetName, args: ReviewFlagBag) -> ReviewFlagBag:
    """Return a copy of ``args`` with the preset applied (explicit flags win)."""
    return _APPLIERS[preset](args)
