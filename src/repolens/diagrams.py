"""Foolproof Mermaid handling: validate → one repair → textual fallback."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_FENCE_RE = re.compile(
    r"```(?:mermaid)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_ALLOWED_HEADERS = ("flowchart", "graph", "sequenceDiagram", "sequencediagram")
_MAX_MERMAID_CHARS = 8_000


@dataclass
class DiagramResult:
    kind: str  # "mermaid" | "textual"
    mermaid: str | None = None
    textual: str | None = None
    image_path: Path | None = None
    notes: list[str] = field(default_factory=list)


def extract_mermaid(raw: str) -> str:
    """Pull Mermaid body from a fenced block or treat whole string as body."""
    text = (raw or "").strip()
    if not text:
        return ""
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    if text.lower().startswith("```"):
        # Unclosed / odd fence — strip first line
        lines = text.splitlines()
        return "\n".join(lines[1:]).strip().removesuffix("```").strip()
    return text


def _has_bare_dotted_edge_nodes(text: str) -> bool:
    """True when an edge uses bare ``file.py`` tokens (Mermaid syntax error)."""
    edge_re = re.compile(
        r"^\s*(\S+)\s*(?:-->|---|==>|-\.->)\s*(\S+)\s*$"
    )
    for line in text.splitlines():
        m = edge_re.match(line)
        if not m:
            continue
        for tok in m.groups():
            if tok[0] in {"[", "(", '"', "'"}:
                continue
            if re.match(r'^[A-Za-z_][\w]*(\["|\(|\[)', tok):
                continue
            if "." in tok:
                return True
    return False


def _mermaid_bare_id(token: str) -> str:
    """Map any node token to a Markdown/Mermaid-safe bare id (no labels)."""
    n = token.strip()
    if not n:
        return "n"
    # id(label) / id[label] / id["label"] → id
    m = re.match(r"^([A-Za-z_][\w]*)\s*[\(\[\"]", n)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z_][\w]*", n):
        return n
    safe = re.sub(r"[^A-Za-z0-9_]", "_", n)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe or safe[0].isdigit():
        safe = "n_" + safe
    return safe or "n"


def normalize_mermaid_node_ids(body: str) -> str:
    """Force bulletproof Mermaid edges for IDE Markdown previews.

    Cursor/VS Code often break Mermaid by:
    - treating ``id[label]`` as Markdown links
    - treating ``>`` in ``-->`` as a blockquote (leaves ``host--``)
    - smart-typography turning `` --> `` into `` → `` / `` →> ``

    So we emit only bare ids and tight undirected edges: ``host---run_mode``
    (no ``>``). Human labels belong in Markdown prose next to the fence.
    """
    text = (body or "").strip()
    if not text:
        return text

    # Allow spaces inside id(label with spaces) on either side of the arrow.
    # Prefer longer operators first so ``---`` is not split as ``--`` + ``-``.
    edge_re = re.compile(
        r"^\s*(.+?)\s*(-->|---|==>|-\.->|→>|→)\s*(.+?)\s*$"
    )
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith(("flowchart", "graph", "sequencediagram")):
            out.append(stripped)
            continue
        m = edge_re.match(stripped)
        if not m:
            # Keep simple bare-id only lines; drop labelled declarations.
            if re.fullmatch(r"[A-Za-z_][\w]*", stripped):
                out.append(stripped)
            continue
        left, _op, right = m.groups()
        # ``---`` avoids ``>`` (Cursor preview blockquote-eats ``-->``).
        out.append(f"{_mermaid_bare_id(left)}---{_mermaid_bare_id(right)}")
    return "\n".join(out)


def validate_mermaid(body: str) -> bool:
    """Structural checks only — no external renderer required."""
    text = (body or "").strip()
    if not text or len(text) > _MAX_MERMAID_CHARS:
        return False
    first = text.splitlines()[0].strip()
    head = first.split(None, 1)[0] if first else ""
    if head not in _ALLOWED_HEADERS and head.lower() not in {
        "flowchart",
        "graph",
        "sequencediagram",
    }:
        return False
    # Reject obviously truncated edges: "A -->" with nothing after
    for line in text.splitlines():
        stripped = line.strip()
        if re.search(r"(-->|--|==>|-\.->)\s*$", stripped):
            return False
    # Need at least one connector or message arrow for a usable diagram
    if not re.search(r"(-->|--|==>|-\.->|->>|-->>)", text):
        return False
    if _has_bare_dotted_edge_nodes(text):
        return False
    return True


def repair_mermaid(body: str) -> str:
    """Best-effort local repair (no LLM). Overridable in tests via patch."""
    text = extract_mermaid(body)
    if not text:
        return ""
    # Drop trailing incomplete edge lines
    lines = [
        ln
        for ln in text.splitlines()
        if not re.search(r"(-->|--|==>|-\.->)\s*$", ln.strip())
    ]
    text = "\n".join(lines).strip()
    if text and not any(
        text.splitlines()[0].strip().split(None, 1)[0].lower().startswith(h.lower())
        for h in ("flowchart", "graph", "sequencediagram")
    ):
        text = "flowchart LR\n" + text
    return normalize_mermaid_node_ids(text)


def textual_fallback(body: str, *, reason: str) -> str:
    """ASCII/structured fallback when Mermaid cannot be validated."""
    snippet = (body or "").strip()
    if len(snippet) > 400:
        snippet = snippet[:400] + "…"
    return (
        "Textual diagram (Mermaid unavailable):\n"
        f"- Reason: {reason}\n"
        "- Flow: [problem] → [impact] → [fix options] → [next step]\n"
        f"- Raw attempt:\n{snippet or '(empty)'}"
    )


def try_render_image(mermaid_body: str, *, out_dir: Path | None = None) -> Path | None:
    """Optional PNG via ``mmdc`` if installed. Raises on hard failure when forced."""
    mmdc = shutil.which("mmdc")
    if not mmdc:
        raise RuntimeError("mmdc not found")
    dest_dir = out_dir or Path(tempfile.mkdtemp(prefix="repolens-mermaid-"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    src = dest_dir / "diagram.mmd"
    png = dest_dir / "diagram.png"
    src.write_text(mermaid_body, encoding="utf-8")
    completed = subprocess.run(
        [mmdc, "-i", str(src), "-o", str(png)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0 or not png.is_file():
        raise RuntimeError(completed.stderr or "mmdc failed")
    return png


def process_diagram(
    raw: str,
    *,
    render_image: str = "never",
    out_dir: Path | None = None,
) -> DiagramResult:
    """Validate Mermaid → one repair → textual fallback; optional image best-effort."""
    notes: list[str] = []
    raw_body = extract_mermaid(raw)
    body = normalize_mermaid_node_ids(raw_body)
    if validate_mermaid(body):
        mermaid = body.strip()
        if body.strip() != raw_body.strip():
            notes.append("diagram.mermaid_normalized")
    else:
        repaired = repair_mermaid(raw).strip()
        if validate_mermaid(repaired):
            mermaid = repaired
            notes.append("diagram.mermaid_repaired")
        else:
            return DiagramResult(
                kind="textual",
                textual=textual_fallback(body or raw, reason="invalid Mermaid after repair"),
                notes=["diagram.mermaid_invalid"],
            )

    image_path: Path | None = None
    mode = (render_image or "never").lower()
    if mode in {"always", "auto"}:
        try:
            image_path = try_render_image(mermaid, out_dir=out_dir)
        except Exception:  # noqa: BLE001 — optional render must never abort explain
            notes.append("diagram.render_skipped")
            if mode == "auto":
                pass

    return DiagramResult(
        kind="mermaid",
        mermaid=mermaid,
        image_path=image_path,
        notes=notes,
    )
