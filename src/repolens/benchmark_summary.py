"""Before/after table for two benchmark rows. No model call."""

from __future__ import annotations

from repolens.providers import CANONICAL_PROVIDERS

_KEY_PROVIDERS = CANONICAL_PROVIDERS - {"ollama"}
_BYTES_PER_MIB = 1024 * 1024
_TABLE_FIELDS = (
    ("wall seconds", "wallSeconds"),
    ("first token seconds", "firstTokenSeconds"),
    ("generation seconds", "generationSeconds"),
    ("chars/s", "charsPerSecond"),
    ("output chars", "outputChars"),
    ("prompt chars", "promptChars"),
    ("prompt tokens", "promptTokens"),
    ("completion tokens", "completionTokens"),
    ("total tokens", "totalTokens"),
    ("repair calls", "repairCalls"),
    ("resumed passes", "resumedPasses"),
    ("queue seconds", "queueWaitSeconds"),
    ("scanner seconds", "scannerSeconds"),
    ("Fast Brain seconds", "fastBrainSeconds"),
)


def require_arm(provider: str | None, arm: str) -> None:
    """Refuse an arm the configured provider cannot run."""
    if arm == "ci":
        return
    if arm == "local" and provider == "ollama":
        return
    if arm == "byok" and provider in _KEY_PROVIDERS:
        return
    raise SystemExit(f"{arm} arm does not match provider {provider}")


def compare_rows(left: dict[str, object], right: dict[str, object]) -> str:
    """After divided by before. Each arm keeps its own token count."""
    if left.get("fixture") != right.get("fixture"):
        raise ValueError("rows are not the same fixture")
    left_name = f"{left.get('label')} ({left.get('arm')})"
    right_name = f"{right.get('label')} ({right.get('arm')})"
    left_rate = _per_thousand(left.get("totalTokens"), left.get("promptChars"))
    right_rate = _per_thousand(right.get("totalTokens"), right.get("promptChars"))
    rows = [("", left_name, right_name, "after/before")]
    for label, key in _TABLE_FIELDS:
        if key not in left and key not in right:
            continue
        rows.append(_metric(label, left.get(key), right.get(key)))
    if "pythonPeakRssBytes" in left or "pythonPeakRssBytes" in right:
        rows.append(_metric("Python peak RSS (MB)", _rss_mb(left), _rss_mb(right)))
    rows.append((
        "tokens / 1000 prompt chars",
        _rate_cell(left_rate, left.get("tokenSource")),
        _rate_cell(right_rate, right.get("tokenSource")),
        _ratio(right_rate, left_rate),
    ))
    table = _align(rows)
    note = (
        "Counts stay in each tokenizer. "
        "A token from one arm is not converted into the other."
    )
    if "missing" not in table:
        return f"{table}\n\n{note}"
    return (
        f"{table}\n\n{note}\n"
        "missing means that number was not reported. "
        "A pass that stopped before the first token, a reused pass, "
        "or a provider that sent no token count leaves the cell empty. "
        "The ratio is missing when either side is empty or the before value is 0. "
        "The Pass lines in the report name the empty pass."
    )


def _align(rows: list[tuple[str, str, str, str]]) -> str:
    widths = [max(len(cell) for cell in column) for column in zip(*rows, strict=True)]
    gap = "  "
    lines = [_pad(rows[0], widths, gap)]
    lines.append(gap.join("-" * width for width in widths))
    lines.extend(_pad(row, widths, gap) for row in rows[1:])
    return "\n".join(lines)


def _pad(row: tuple[str, str, str, str], widths: list[int], gap: str) -> str:
    label, left, right, ratio = row
    return gap.join((
        label.ljust(widths[0]),
        left.rjust(widths[1]),
        right.rjust(widths[2]),
        ratio.rjust(widths[3]),
    ))


def _metric(name: str, left: object, right: object) -> tuple[str, str, str, str]:
    return (name, _cell(left), _cell(right), _ratio(right, left))


def _rss_mb(row: dict[str, object]) -> float | None:
    raw = row.get("pythonPeakRssBytes")
    if not isinstance(raw, (int, float)):
        return None
    return round(float(raw) / _BYTES_PER_MIB, 1)


def _per_thousand(tokens: object, chars: object) -> float | None:
    if not isinstance(tokens, (int, float)) or not isinstance(chars, (int, float)):
        return None
    if chars == 0:
        return None
    return round(float(tokens) / float(chars) * 1000, 1)


def _rate_cell(rate: float | None, source: object) -> str:
    if rate is None or not source:
        return "missing"
    return f"{rate:.1f} {source}"


def _cell(value: object) -> str:
    if value is None:
        return "missing"
    return str(value)


def _ratio(after: object, before: object) -> str:
    if not isinstance(after, (int, float)) or not isinstance(before, (int, float)):
        return "missing"
    if before == 0:
        return "missing"
    return f"{float(after) / float(before):.2f}"
