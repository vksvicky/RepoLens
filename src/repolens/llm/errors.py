"""LLM error types and helpers."""

from __future__ import annotations


class LlmError(RuntimeError):
    """Provider or parse failure."""


def _provider_error_hint(
    *,
    status_code: int,
    detail: str,
    provider: str | None,
    model: str,
) -> str:
    from repolens.llm.setup import list_ollama_models

    hint = ""
    if status_code == 404 and provider == "ollama":
        installed = list_ollama_models()
        if installed:
            hint = (
                f" Model {model!r} is not installed. "
                f"Installed: {', '.join(installed[:8])}. "
                f"Run: repolens init --provider ollama --model {installed[0]} --force"
            )
        else:
            hint = (
                f" Model {model!r} may be missing — run: ollama list "
                f"then either `ollama pull {model}` or "
                f"`repolens init --provider ollama --model <name> --force`."
            )
    return (
        f"LLM provider error {status_code}"
        + (f": {detail}" if detail else "")
        + hint
    )


def _timeout_error(timeout: float, model: str, provider: str | None) -> LlmError:
    return LlmError(
        f"LLM timed out after {timeout:g}s waiting for the first token "
        f"from {model} ({provider}). "
        "Finished passes are kept. Re-run when the local model is free."
    )


