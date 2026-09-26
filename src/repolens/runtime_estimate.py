"""Pre-flight Slow Brain wall-time estimates (#15). Pure — no network."""

from __future__ import annotations

# Seconds per file per pass (rough empirical bands from dogfood).
_SEC_PER_FILE: dict[str, float] = {
    "ollama": 7.0,  # local 32B often ≫ this; underestimate slightly for small packs
    "gemini": 1.2,
    "openai": 1.0,
    "anthropic": 1.0,
    "azure": 1.0,
    "groq": 0.4,
    "mistral": 0.8,
    "openrouter": 1.0,
    "together": 0.8,
    "fireworks": 0.6,
    "deepseek": 0.9,
    "openai_compatible": 1.0,
}
_DEFAULT_SEC = 1.5


def estimate_deep_runtime_minutes(
    *,
    files: int,
    passes: int,
    provider: str,
) -> int:
    """Return a coarse lower-bound minutes estimate (integer)."""
    if files <= 0 or passes <= 0:
        return 0
    key = (provider or "unknown").strip().lower()
    per = _SEC_PER_FILE.get(key, _DEFAULT_SEC)
    # Local Ollama 32B dogfood: ~200 files × 3 passes ≈ 70+ minutes; scale up.
    if key == "ollama":
        per = 8.0
    seconds = files * passes * per
    return max(1, int(round(seconds / 60.0)))


def estimate_deep_runtime(
    *,
    files: int,
    passes: int,
    provider: str,
) -> str:
    """Human-readable pre-flight line for progress / stderr."""
    if files <= 0:
        return "Slow Brain estimate: no LLM files in pack (0 minutes)"
    minutes = estimate_deep_runtime_minutes(
        files=files, passes=passes, provider=provider
    )
    provider_label = (provider or "unknown").strip() or "unknown"
    if minutes < 5:
        band = f"~{minutes} min"
    elif minutes < 60:
        band = f"~{minutes}–{minutes + max(5, minutes // 3)} min"
    else:
        hours = minutes / 60.0
        band = f"~{hours:.1f}–{hours * 1.4:.1f} h (local large models often hit the high end)"
    return (
        f"Slow Brain estimate: {files} file(s) × {passes} pass(es) via {provider_label} "
        f"→ {band}"
    )
