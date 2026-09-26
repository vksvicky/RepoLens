"""Map ratchet breaches to newly added import lines in a unified diff (G2 FR5)."""

from __future__ import annotations

import re
from collections.abc import Sequence

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_IMPORT_FROM_RE = re.compile(
    r"^from\s+([\w.]+)\s+import\s+(.+)$",
)
_IMPORT_BARE_RE = re.compile(r"^import\s+(.+)$")


def parse_added_import_lines(unified_diff: str) -> list[tuple[str, int, str]]:
    """Return ``(path, new_file_line, stripped_line)`` for each added import."""
    out: list[tuple[str, int, str]] = []
    current_file = ""
    new_line = 0

    for raw in unified_diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
            continue

        hunk = _HUNK_RE.match(raw)
        if hunk:
            new_line = int(hunk.group(1))
            continue

        if not current_file:
            continue

        if raw.startswith("+"):
            added = raw[1:]
            if _is_import_line(added):
                out.append((current_file, new_line, added.strip()))
            new_line += 1
        elif raw.startswith(" "):
            new_line += 1

    return out


def anchor_ratchet_breach(
    *,
    diff_text: str,
    added_fingerprints: Sequence[Sequence[str]],
    representative_paths: Sequence[str] | None = None,
) -> tuple[str, int, str] | None:
    """Pick a diff line that best explains a ratchet breach, if any."""
    if not added_fingerprints:
        return None

    fingerprint_modules = {
        mod for fp in added_fingerprints for mod in fp if mod
    }
    if not fingerprint_modules:
        return None

    fingerprint_tails = {mod.rsplit(".", 1)[-1] for mod in fingerprint_modules}
    rep_set = set(representative_paths or ())
    candidates = parse_added_import_lines(diff_text)
    if not candidates:
        return None

    best: tuple[str, int, str] | None = None
    best_rank: tuple[int, str, int, str] | None = None
    for path, line, text in candidates:
        score = _anchor_score(
            path=path,
            import_text=text,
            fingerprint_modules=fingerprint_modules,
            fingerprint_tails=fingerprint_tails,
            representative_paths=rep_set,
        )
        if score < 0:
            continue
        item = (path, line, text)
        rank = (-score, path, line, text)
        if best_rank is None or rank < best_rank:
            best = item
            best_rank = rank

    return best


def format_github_actions_error(file: str, line: int, message: str) -> str:
    """Format a GitHub Actions ``::error`` workflow command."""
    return f"::error file={file},line={line}::{_escape_workflow(message)}"


def _escape_workflow(text: str) -> str:
    return (
        text.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
    )


def _is_import_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    return stripped.startswith("import ") or stripped.startswith("from ")


def _path_to_module(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.endswith("/__init__.py"):
        normalized = normalized[: -len("/__init__.py")]
    elif normalized.endswith(".py"):
        normalized = normalized[: -3]
    return normalized.replace("/", ".")


def _imported_modules(line: str) -> set[str]:
    stripped = line.strip()
    modules: set[str] = set()

    m_from = _IMPORT_FROM_RE.match(stripped)
    if m_from:
        base = m_from.group(1)
        modules.add(base)
        tail = m_from.group(2).split("#", 1)[0].strip()
        if tail.startswith("("):
            inner = tail.strip("()")
            names = [p.strip().split()[0] for p in inner.split(",") if p.strip()]
        else:
            names = [p.strip().split()[0] for p in tail.split(",") if p.strip()]
        for name in names:
            name = name.split(" as ")[0].strip()
            if name == "*":
                continue
            if "." in name:
                modules.add(name)
            else:
                modules.add(f"{base}.{name}")
        return modules

    m_imp = _IMPORT_BARE_RE.match(stripped)
    if m_imp:
        tail = m_imp.group(1).split("#", 1)[0]
        for part in tail.split(","):
            part = part.strip()
            if not part:
                continue
            mod = part.split(" as ")[0].strip()
            modules.add(mod)
    return modules


def _anchor_score(
    *,
    path: str,
    import_text: str,
    fingerprint_modules: set[str],
    fingerprint_tails: set[str],
    representative_paths: set[str],
) -> int:
    file_module = _path_to_module(path)
    imported = _imported_modules(import_text)

    import_hit = bool(imported & fingerprint_modules)
    file_hit = file_module in fingerprint_modules
    tail_hit = (
        file_module.rsplit(".", 1)[-1] in fingerprint_tails
        or bool({m.rsplit(".", 1)[-1] for m in imported} & fingerprint_tails)
    )

    if not (import_hit or file_hit or tail_hit):
        return -1

    score = 0
    if import_hit:
        score += 100
    if file_hit:
        score += 50
    if tail_hit:
        score += 10
    if path in representative_paths:
        score += 1000
    return score
