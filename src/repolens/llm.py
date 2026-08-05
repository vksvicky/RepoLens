"""LLM provider adapters (OpenAI-compatible + Ollama)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

import httpx

from repolens.config import ModelConfig, resolve_api_key
from repolens.schema import FindingReport

SYSTEM_PROMPT = """You are RepoLens, a rigorous code reviewer.
Return ONLY valid JSON matching the FindingReport schema:
{
  "schemaVersion": "1.0",
  "confidence": 0-100,
  "summary": {"critical":0,"high":0,"medium":0,"low":0},
  "issues": [{
    "severity":"CRITICAL|HIGH|MEDIUM|LOW",
    "priority":"P1|P2|P3",
    "category":"string",
    "file":"path",
    "line":1,
    "title":"string",
    "explanation":"string",
    "impact":"string",
    "recommendedFix":"string",
    "codeExample":"string",
    "fixTiming":"immediately|before launch|after launch|if time permits",
    "cwe": null,
    "owasp": null
  }],
  "durabilityGaps": ["string"],
  "scores": null
}
Critical and High issues MUST include non-empty impact and codeExample.
Be evidence-based. Prefer fewer high-confidence findings over speculation.
"""


class LlmError(RuntimeError):
    """Provider or parse failure."""


OLLAMA_PROBE_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_FALLBACK_MODEL = "llama3.1"
DEFAULT_LLM_TIMEOUT = 120.0
DEFAULT_OLLAMA_TIMEOUT = 900.0


def resolve_llm_timeout(model_cfg: ModelConfig) -> float:
    """Seconds for the chat-completions HTTP call."""
    if model_cfg.timeout_seconds is not None and model_cfg.timeout_seconds > 0:
        return float(model_cfg.timeout_seconds)
    if model_cfg.provider == "ollama":
        return DEFAULT_OLLAMA_TIMEOUT
    return DEFAULT_LLM_TIMEOUT


def detect_ollama(*, timeout: float = 0.5) -> bool:
    """Return True if a local Ollama HTTP API answers on the default port."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(OLLAMA_PROBE_URL)
        return response.status_code < 500
    except (httpx.HTTPError, OSError):
        return False


def list_ollama_models(*, timeout: float = 1.0) -> list[str]:
    """Return model names reported by the local Ollama `/api/tags` endpoint."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(OLLAMA_PROBE_URL)
        if response.status_code >= 500:
            return []
        payload = response.json()
    except (httpx.HTTPError, OSError, json.JSONDecodeError, ValueError):
        return []
    names: list[str] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name:
            names.append(str(name))
    return names


def pick_ollama_model(
    installed: list[str], *, fallback: str = OLLAMA_FALLBACK_MODEL
) -> str:
    """Prefer an already-installed model; only use fallback when the list is empty."""
    return installed[0] if installed else fallback


def resolve_ollama_model(
    explicit: str | None = None,
) -> tuple[str, list[str]]:
    """Return (model_to_use, installed_models). Explicit `--model` always wins."""
    installed = list_ollama_models()
    if explicit and explicit.strip():
        return explicit.strip(), installed
    return pick_ollama_model(installed), installed


def provider_setup_hints() -> list[str]:
    """Actionable next steps when [model].provider is missing."""
    from repolens.config import user_config_path

    cfg = user_config_path()
    hints = [
        f"RepoLens needs a one-time model config at: {cfg}",
        "Having Ollama installed is not enough — point RepoLens at it with:",
        "  repolens init --provider ollama",
        "Or use a cloud key:  repolens init --provider openai",
        "Or skip the LLM:  repolens review --path … --dry-run",
        "                 repolens review --path … --scanners-only",
        "Docs: docs/setup-ai-and-scanners.md",
    ]
    if detect_ollama():
        installed = list_ollama_models()
        if installed:
            chosen = pick_ollama_model(installed)
            listed = ", ".join(installed[:5]) + ("…" if len(installed) > 5 else "")
            hints.insert(
                1,
                f"Detected Ollama with installed model(s): {listed} — "
                f"run:  repolens init --provider ollama  "
                f"(will use {chosen} unless you pass --model)",
            )
        else:
            hints.insert(
                1,
                "Detected Ollama running on http://127.0.0.1:11434 (no models yet) — "
                f"run:  ollama pull {OLLAMA_FALLBACK_MODEL}  then  "
                "repolens init --provider ollama",
            )
            hints.insert(
                2,
                "Or pull any model you prefer, then: "
                "repolens init --provider ollama --model <name>",
            )
    return hints


def default_base_url(provider: str | None) -> str:
    return {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "ollama": "http://127.0.0.1:11434/v1",
        "openai_compatible": "http://127.0.0.1:11434/v1",
    }.get(provider or "", "https://api.openai.com/v1")


def default_model(provider: str | None) -> str:
    if provider in {"ollama", "openai_compatible"}:
        return resolve_ollama_model(None)[0]
    return {
        "openai": "gpt-4.1-mini",
        "anthropic": "claude-sonnet-4-20250514",
        "deepseek": "deepseek-chat",
    }.get(provider or "", "gpt-4.1-mini")


def analyze(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
) -> FindingReport:
    content = analyze_raw(prompt, model_cfg, client=client)
    return parse_report_json(content)


def analyze_raw(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    if not model_cfg.provider:
        raise LlmError(
            "No model provider configured. "
            + " ".join(provider_setup_hints()[:3])
        )

    # Anthropic uses its Messages API; others use OpenAI-compatible chat completions.
    if model_cfg.provider == "anthropic":
        return _analyze_anthropic(
            prompt, model_cfg, client=client, on_delta=on_delta
        )

    return _analyze_openai_compatible(
        prompt, model_cfg, client=client, on_delta=on_delta
    )


def _provider_error_hint(
    *,
    status_code: int,
    detail: str,
    provider: str | None,
    model: str,
) -> str:
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
        f"LLM timed out after {timeout:g}s talking to {model} ({provider}). "
        "Large repos + local models often need more time. Try: "
        f"`repolens review --timeout {int(timeout * 2)} …`, "
        "set `timeout_seconds` in ~/.config/repolens/config.toml, "
        "or narrow scope with `--mode diff --since HEAD~20`, "
        "`--scanners-only`, or `--dry-run`."
    )


def _parse_sse_chat_chunk(line: str) -> str | None:
    """Extract delta content from one OpenAI-compatible SSE ``data:`` line."""
    text = line.strip()
    if not text.startswith("data:"):
        return None
    payload = text[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    choices = data.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content if isinstance(content, str) else None


def _analyze_openai_compatible(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    api_key = resolve_api_key(model_cfg)
    if model_cfg.provider != "ollama" and not api_key:
        raise LlmError(
            f"Missing API key. Export {model_cfg.api_key_env or 'the provider key env var'} "
            "or use provider=ollama for local AI."
        )

    base = (model_cfg.base_url or default_base_url(model_cfg.provider)).rstrip("/")
    model = model_cfg.model or default_model(model_cfg.provider)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Stream when a progress callback is provided, or always for local Ollama /
    # OpenAI-compatible BYOK so wait UX can show chars received.
    use_stream = on_delta is not None or model_cfg.provider in {
        "ollama",
        "openai",
        "deepseek",
        "openai_compatible",
    }

    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    if use_stream:
        payload["stream"] = True

    timeout = resolve_llm_timeout(model_cfg)
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        if use_stream:
            return _stream_openai_compatible(
                client,
                base=base,
                headers=headers,
                payload=payload,
                model=model,
                provider=model_cfg.provider,
                timeout=timeout,
                on_delta=on_delta,
            )
        response = client.post(f"{base}/chat/completions", headers=headers, json=payload)
        if response.status_code >= 400:
            detail = (response.text or "").strip()
            if len(detail) > 300:
                detail = detail[:300] + "…"
            raise LlmError(
                _provider_error_hint(
                    status_code=response.status_code,
                    detail=detail,
                    provider=model_cfg.provider,
                    model=model,
                )
            )
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content
    except httpx.TimeoutException as exc:
        raise _timeout_error(timeout, model, model_cfg.provider) from exc
    except (KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
        raise LlmError(f"Failed to complete LLM analysis: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def _stream_openai_compatible(
    client: httpx.Client,
    *,
    base: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    model: str,
    provider: str | None,
    timeout: float,
    on_delta: Callable[[str], None] | None,
) -> str:
    """Accumulate streamed chat.completion chunks; invoke ``on_delta`` per piece."""
    parts: list[str] = []
    try:
        with client.stream(
            "POST",
            f"{base}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code >= 400:
                detail = (response.read().decode("utf-8", errors="replace") or "").strip()
                if len(detail) > 300:
                    detail = detail[:300] + "…"
                raise LlmError(
                    _provider_error_hint(
                        status_code=response.status_code,
                        detail=detail,
                        provider=provider,
                        model=model,
                    )
                )
            for line in response.iter_lines():
                if not line:
                    continue
                piece = _parse_sse_chat_chunk(line)
                if piece is None:
                    continue
                parts.append(piece)
                if on_delta is not None:
                    on_delta(piece)
    except httpx.TimeoutException as exc:
        raise _timeout_error(timeout, model, provider) from exc
    content = "".join(parts)
    if not content.strip():
        raise LlmError("LLM stream completed with empty content")
    return content


def _parse_anthropic_sse_text_delta(line: str) -> str | None:
    """Extract text from an Anthropic ``content_block_delta`` SSE data line."""
    text = line.strip()
    if not text.startswith("data:"):
        return None
    payload = text[len("data:") :].strip()
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if data.get("type") != "content_block_delta":
        return None
    delta = data.get("delta") or {}
    if delta.get("type") != "text_delta":
        return None
    piece = delta.get("text")
    return piece if isinstance(piece, str) else None


def _analyze_anthropic(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    api_key = resolve_api_key(model_cfg) or resolve_api_key(
        ModelConfig(provider="anthropic", api_key_env="ANTHROPIC_API_KEY")
    )
    if not api_key:
        raise LlmError("Missing ANTHROPIC_API_KEY for provider=anthropic")

    model = model_cfg.model or default_model("anthropic")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    timeout = resolve_llm_timeout(model_cfg)
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        return _stream_anthropic(
            client,
            headers=headers,
            payload=payload,
            timeout=timeout,
            on_delta=on_delta,
        )
    except httpx.TimeoutException as exc:
        raise LlmError(
            f"Anthropic timed out after {timeout:g}s. "
            f"Try `--timeout {int(timeout * 2)}` or set timeout_seconds in config."
        ) from exc
    except (KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
        raise LlmError(f"Failed to complete Anthropic analysis: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def _stream_anthropic(
    client: httpx.Client,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    on_delta: Callable[[str], None] | None,
) -> str:
    """Accumulate Anthropic Messages SSE ``text_delta`` chunks."""
    parts: list[str] = []
    try:
        with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code >= 400:
                detail = (
                    response.read().decode("utf-8", errors="replace") or ""
                ).strip()
                if len(detail) > 300:
                    detail = detail[:300] + "…"
                raise LlmError(
                    f"Anthropic error {response.status_code}"
                    + (f": {detail}" if detail else "")
                )
            for line in response.iter_lines():
                if not line:
                    continue
                piece = _parse_anthropic_sse_text_delta(line)
                if piece is None:
                    continue
                parts.append(piece)
                if on_delta is not None:
                    on_delta(piece)
    except httpx.TimeoutException as exc:
        raise LlmError(
            f"Anthropic timed out after {timeout:g}s. "
            f"Try `--timeout {int(timeout * 2)}` or set timeout_seconds in config."
        ) from exc
    content = "".join(parts)
    if not content.strip():
        raise LlmError("Anthropic stream completed with empty content")
    return content


def _first_str(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key not in data:
            continue
        val = data[key]
        if val is None:
            continue
        text = str(val).strip()
        if text:
            return text
    return default


def _coerce_severity(raw: Any) -> str:
    text = str(raw or "").strip().upper().replace(" ", "_")
    aliases = {
        "CRIT": "CRITICAL",
        "CRITICAL": "CRITICAL",
        "P1": "HIGH",
        "HIGH": "HIGH",
        "SEVERE": "HIGH",
        "ERROR": "HIGH",
        "P2": "MEDIUM",
        "MEDIUM": "MEDIUM",
        "MODERATE": "MEDIUM",
        "WARN": "MEDIUM",
        "WARNING": "MEDIUM",
        "P3": "LOW",
        "LOW": "LOW",
        "INFO": "LOW",
        "INFORMATIONAL": "LOW",
        "MINOR": "LOW",
    }
    if text in aliases:
        return aliases[text]
    for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if name in text:
            return name
    return "MEDIUM"


def _priority_for_severity(severity: str) -> str:
    if severity in {"CRITICAL", "HIGH"}:
        return "P1"
    if severity == "MEDIUM":
        return "P2"
    return "P3"


def _coerce_priority(raw: Any, *, severity: str) -> str:
    text = str(raw or "").strip().upper()
    if text in {"P1", "P2", "P3"}:
        return text
    if text in {"1", "HIGH", "CRITICAL"}:
        return "P1"
    if text in {"2", "MEDIUM"}:
        return "P2"
    if text in {"3", "LOW"}:
        return "P3"
    return _priority_for_severity(severity)


def _coerce_line(raw: Any) -> int:
    if isinstance(raw, bool):
        return 1
    if isinstance(raw, int):
        return raw if raw >= 1 else 1
    if isinstance(raw, float):
        return int(raw) if raw >= 1 else 1
    if isinstance(raw, str):
        match = re.search(r"\d+", raw)
        if match:
            value = int(match.group(0))
            return value if value >= 1 else 1
    return 1


def _coerce_fix_timing(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    allowed = {
        "immediately",
        "before launch",
        "after launch",
        "if time permits",
    }
    if text in allowed:
        return text
    if "immediate" in text:
        return "immediately"
    if "after" in text:
        return "after launch"
    if "permit" in text or "later" in text:
        return "if time permits"
    return "before launch"


def _coerce_issue(raw: Any) -> dict[str, Any] | None:
    """Normalize one issue object; drop entries that cannot become useful findings."""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        raw = {"title": text[:120], "explanation": text}
    if not isinstance(raw, dict):
        return None

    # Flatten common wrappers
    for nest_key in ("issue", "finding", "item"):
        nested = raw.get(nest_key)
        if isinstance(nested, dict):
            merged = dict(nested)
            merged.update({k: v for k, v in raw.items() if k != nest_key})
            raw = merged
            break

    sev_source = raw.get("severity") or raw.get("Severity") or raw.get("level")
    if sev_source is None or str(sev_source).strip() == "":
        sev_source = raw.get("priority")  # e.g. only "P1" provided
    severity = _coerce_severity(sev_source)
    priority = _coerce_priority(
        raw.get("priority") or raw.get("Priority") or raw.get("pri"),
        severity=severity,
    )

    title = _first_str(raw, "title", "name", "summary", "heading", default="")
    explanation = _first_str(
        raw,
        "explanation",
        "description",
        "details",
        "detail",
        "rationale",
        "message",
        default="",
    )
    if not title and explanation:
        title = explanation[:120]
    if not explanation and title:
        explanation = title
    if not title and not explanation:
        return None

    recommended = _first_str(
        raw,
        "recommendedFix",
        "recommended_fix",
        "recommendation",
        "fix",
        "remediation",
        "solution",
        default="Review and remediate manually.",
    )
    impact = _first_str(raw, "impact", "risk", "consequence", default="")
    code_example = _first_str(
        raw, "codeExample", "code_example", "example", "snippet", default=""
    )
    # Fill Critical/High gates only when the model omitted the keys entirely
    # (explicit empty strings still fail validation — keep that contract).
    if severity in {"CRITICAL", "HIGH"}:
        if not impact and not any(k in raw for k in ("impact", "risk", "consequence")):
            impact = "(Model omitted impact — verify manually.)"
        if not code_example and not any(
            k in raw for k in ("codeExample", "code_example", "example", "snippet")
        ):
            code_example = "// Model omitted codeExample — verify manually.\n"

    file_path = _first_str(
        raw,
        "file",
        "path",
        "filePath",
        "file_path",
        "filename",
        "location",
        default="(unspecified)",
    )
    category = _first_str(
        raw, "category", "type", "kind", "area", default="General"
    )

    return {
        "severity": severity,
        "priority": priority,
        "category": category,
        "file": file_path,
        "line": _coerce_line(raw.get("line") or raw.get("lineNumber") or raw.get("lineno")),
        "title": title,
        "explanation": explanation,
        "impact": impact,
        "recommendedFix": recommended,
        "codeExample": code_example,
        "fixTiming": _coerce_fix_timing(
            raw.get("fixTiming") or raw.get("fix_timing") or raw.get("when")
        ),
        "cwe": raw.get("cwe"),
        "owasp": raw.get("owasp"),
    }


def _coerce_report_payload(raw: Any) -> dict[str, Any]:
    """Normalize common local-LLM JSON mistakes before Pydantic validation."""
    if not isinstance(raw, dict):
        raise TypeError(f"FindingReport JSON must be an object, got {type(raw).__name__}")
    data = dict(raw)

    conf = data.get("confidence", 0)
    if isinstance(conf, str):
        conf = conf.strip().rstrip("%")
        try:
            conf = int(float(conf))
        except ValueError:
            conf = 0
    elif isinstance(conf, float):
        conf = int(conf)
    data["confidence"] = conf

    summary = data.get("summary")
    if not isinstance(summary, dict):
        # Models sometimes emit a string or list; recount_summary will fix counts.
        data["summary"] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
    else:
        fixed: dict[str, Any] = {}
        for key in ("critical", "high", "medium", "low"):
            val = summary.get(key, 0)
            if isinstance(val, str):
                try:
                    val = int(float(val.strip()))
                except ValueError:
                    val = 0
            elif isinstance(val, float):
                val = int(val)
            fixed[key] = val if isinstance(val, int) else 0
        data["summary"] = fixed

    issues_raw = data.get("issues")
    if not isinstance(issues_raw, list):
        # Some models nest findings under findings/results
        for alt in ("findings", "results", "problems"):
            if isinstance(data.get(alt), list):
                issues_raw = data[alt]
                break
        else:
            issues_raw = []
    coerced_issues: list[dict[str, Any]] = []
    for item in issues_raw:
        issue = _coerce_issue(item)
        if issue is not None:
            coerced_issues.append(issue)
    data["issues"] = coerced_issues

    gaps = data.get("durabilityGaps")
    if gaps is None:
        gaps = data.get("durability_gaps") or data.get("gaps") or []
    if isinstance(gaps, str):
        gaps = [gaps] if gaps.strip() else []
    if not isinstance(gaps, list):
        gaps = []
    data["durabilityGaps"] = [str(g) for g in gaps if str(g).strip()]

    return data


def parse_report_json(content: str) -> FindingReport:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        raw = json.loads(match.group(0))
    report = FindingReport.model_validate(_coerce_report_payload(raw))
    # Keep summary consistent with issues when model drifts
    counted = report.recount_summary()
    report.summary = counted
    return report


def repair_prompt(original: str, error: str) -> str:
    return (
        f"{original}\n\n---\nYour previous JSON was invalid: {error}\n"
        "Return corrected FindingReport JSON only with this exact shape:\n"
        '{"schemaVersion":"1.0","confidence":<integer 0-100>,'
        '"summary":{"critical":0,"high":0,"medium":0,"low":0},'
        '"issues":[...],"durabilityGaps":[]}\n'
        "confidence MUST be a JSON number (not a string). "
        "summary MUST be an object with integer fields. "
        "Each issue MUST use keys: severity (CRITICAL|HIGH|MEDIUM|LOW), "
        "priority (P1|P2|P3), category, file, line (integer), title, "
        "explanation, recommendedFix; Critical/High also need impact and codeExample."
    )
