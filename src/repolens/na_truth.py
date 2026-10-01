"""Reject vacuous N/A claims contradicted by inventory evidence."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from repolens.inventory import FileEntry

_NA_RE = re.compile(
    r"(?:coverage:)?(?P<id>[^\s:]+)\s*:\s*N/A\s*[—\-]\s*(?P<reason>.+)$",
    re.IGNORECASE,
)

# Checklist id → path/content keywords that contradict "absent" N/A reasons.
_ABSENCE_HINTS: dict[str, tuple[str, ...]] = {
    "sec.injection": ("sql", "execute(", "cursor.execute", "shell=True", "subprocess"),
    "sec.secrets": (".env", "password", "api_key", "secret", "token"),
    "sec.auth": ("auth", "jwt", "oauth", "session", "login"),
    "rel.edge_cases": ("except", "timeout", "retry"),
    "arch.testing": ("test_", "/tests/", "pytest", "unittest"),
}


def _inventory_blob(entries: Sequence[FileEntry], *, sample: int = 80) -> str:
    parts = [e.relative.lower() for e in entries[:sample]]
    return "\n".join(parts)


def reject_false_na_claims(
    gaps: list[str],
    entries: Sequence[FileEntry],
    *,
    root: Path | None = None,
) -> list[str]:
    """Append hallucination_residual when N/A claims absence but inventory contradicts."""
    blob = _inventory_blob(entries)
    extra: list[str] = []
    for gap in gaps:
        match = _NA_RE.match(gap.strip())
        if not match:
            continue
        cid = match.group("id").strip()
        reason = match.group("reason").strip().lower()
        if not any(
            token in reason
            for token in ("no ", "none", "absent", "not present", "does not", "don't", "without")
        ):
            continue
        hints = _ABSENCE_HINTS.get(cid)
        if not hints:
            # Also try prefix match e.g. sec.injection.foo
            for key, values in _ABSENCE_HINTS.items():
                if cid.startswith(key) or key.startswith(cid):
                    hints = values
                    break
        if not hints:
            continue
        if any(h in blob for h in hints):
            residual = f"hallucination_residual:{cid}: inventory contradicts N/A ({reason[:80]})"
            if residual not in gaps and residual not in extra:
                extra.append(residual)
        elif root is not None:
            # Optional deeper peek for common secret filenames
            for hint in hints:
                if "/" in hint or hint.startswith("."):
                    if (root / hint.lstrip("./")).exists():
                        residual = (
                            f"hallucination_residual:{cid}: path {hint} exists"
                        )
                        if residual not in gaps and residual not in extra:
                            extra.append(residual)
                        break
    return list(gaps) + extra
