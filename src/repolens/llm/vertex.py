"""Google Vertex AI Gemini transport (Phase 9 follow-up #58).

Reuses Gemini SSE parsing. Auth is hybrid: env access token first, then optional
``google-auth`` ADC (``pip install 'repolens-audit[vertex]'``).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from urllib.parse import quote

import httpx

from repolens.config import ModelConfig
from repolens.llm.errors import LlmError
from repolens.llm.gemini import gemini_generate_payload, stream_gemini_sse
from repolens.llm.setup import default_model, resolve_llm_timeout

DEFAULT_VERTEX_MODEL = "gemini-2.0-flash"
DEFAULT_VERTEX_LOCATION = "us-central1"
_CLOUD_PLATFORM_SCOPE = ("https://www.googleapis.com/auth/cloud-platform",)


def resolve_vertex_project(model_cfg: ModelConfig | None = None) -> str:
    """Resolve GCP project id from env (config base_url may embed project later)."""
    del model_cfg  # reserved for future [model] project field
    for key in (
        "VERTEX_PROJECT",
        "GOOGLE_CLOUD_PROJECT",
        "GCLOUD_PROJECT",
        "GCP_PROJECT",
    ):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    raise LlmError(
        "Vertex AI requires a GCP project id. Set VERTEX_PROJECT or "
        "GOOGLE_CLOUD_PROJECT (or run gcloud config set project …)."
    )


def resolve_vertex_location() -> str:
    return (
        (os.environ.get("VERTEX_LOCATION") or "").strip()
        or (os.environ.get("GOOGLE_CLOUD_REGION") or "").strip()
        or DEFAULT_VERTEX_LOCATION
    )


def resolve_vertex_token() -> str:
    """Hybrid Vertex auth: env token, then optional google-auth ADC."""
    for key in ("VERTEX_ACCESS_TOKEN", "GOOGLE_OAUTH_ACCESS_TOKEN"):
        token = (os.environ.get(key) or "").strip()
        if token:
            return token
    try:
        import google.auth  # type: ignore[import-untyped]
        import google.auth.transport.requests  # type: ignore[import-untyped]
    except ImportError as exc:
        raise LlmError(
            "Vertex AI authentication failed: neither VERTEX_ACCESS_TOKEN is set, "
            "nor is 'google-auth' installed for automatic ADC. "
            "Set VERTEX_ACCESS_TOKEN=$(gcloud auth print-access-token) or run: "
            "pip install 'repolens-audit[vertex]'"
        ) from exc
    try:
        creds, _project = google.auth.default(scopes=list(_CLOUD_PLATFORM_SCOPE))
        creds.refresh(google.auth.transport.requests.Request())
        token = getattr(creds, "token", None)
        if not token:
            raise LlmError("google-auth ADC returned an empty access token")
        return str(token)
    except LlmError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface ADC failures as LlmError
        raise LlmError(
            f"Vertex AI ADC failed: {exc}. "
            "Set VERTEX_ACCESS_TOKEN=$(gcloud auth print-access-token) or fix ADC."
        ) from exc


def vertex_stream_url(
    *,
    project: str,
    location: str,
    model: str,
    base_url: str | None = None,
) -> str:
    model_path = quote(model, safe=".-_/")
    if base_url:
        root = base_url.rstrip("/")
        return (
            f"{root}/v1/projects/{quote(project, safe='')}"
            f"/locations/{quote(location, safe='')}"
            f"/publishers/google/models/{model_path}:streamGenerateContent"
        )
    host = f"{location}-aiplatform.googleapis.com"
    return (
        f"https://{host}/v1/projects/{quote(project, safe='')}"
        f"/locations/{quote(location, safe='')}"
        f"/publishers/google/models/{model_path}:streamGenerateContent"
    )


def analyze_vertex(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    token = resolve_vertex_token()
    project = resolve_vertex_project(model_cfg)
    location = resolve_vertex_location()
    model = model_cfg.model or default_model("vertex") or DEFAULT_VERTEX_MODEL
    url = vertex_stream_url(
        project=project,
        location=location,
        model=model,
        base_url=model_cfg.base_url,
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = gemini_generate_payload(prompt)
    timeout = resolve_llm_timeout(model_cfg)
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        return stream_gemini_sse(
            client,
            url=url,
            headers=headers,
            payload=payload,
            timeout=timeout,
            on_delta=on_delta,
            label="Vertex AI",
        )
    finally:
        if owns_client:
            client.close()
