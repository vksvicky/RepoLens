"""Best-effort live status from local providers (e.g. Ollama) during long waits."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def ollama_running_summary(base_url: str | None = None) -> str | None:
    """Return a short status string from Ollama ``/api/ps``, or None if unavailable.

    Does not raise — heartbeat paths must stay best-effort.
    """
    root = (base_url or "http://127.0.0.1:11434").rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    url = f"{root}/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data: dict[str, Any] = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None

    models = data.get("models") or []
    if not models:
        return "Ollama: idle / waiting for first token (HTTP request in flight)"

    parts: list[str] = []
    for item in models[:2]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "?")
        size = item.get("size")
        size_gb = f", ~{int(size) / (1024**3):.1f} GiB loaded" if isinstance(size, int) else ""
        # token counts when present (varies by Ollama version)
        eval_count = item.get("eval_count") or item.get("token_count")
        tokens = f", {eval_count} tokens" if isinstance(eval_count, int) else ""
        parts.append(f"{name} running{size_gb}{tokens}")
    if not parts:
        return "Ollama: model loaded (details unavailable)"
    return "Ollama: " + "; ".join(parts)
