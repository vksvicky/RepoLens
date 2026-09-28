"""Amazon Bedrock Converse stream transport (Phase 9 follow-up #58).

SigV4 over httpx (stdlib). Response is AWS event-stream; text deltas come from
``contentBlockDelta`` payloads. Optional ``botocore`` improves decode robustness
(``pip install 'repolens-audit[bedrock]'``) but is not required for tests/CI mocks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import struct
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from repolens.config import ModelConfig
from repolens.llm.errors import LlmError
from repolens.llm.setup import SYSTEM_PROMPT, default_model, resolve_llm_timeout

DEFAULT_BEDROCK_MODEL = "amazon.nova-lite-v1:0"
DEFAULT_BEDROCK_REGION = "us-east-1"


def resolve_bedrock_region() -> str:
    return (
        (os.environ.get("AWS_REGION") or "").strip()
        or (os.environ.get("AWS_DEFAULT_REGION") or "").strip()
        or DEFAULT_BEDROCK_REGION
    )


def resolve_aws_credentials() -> tuple[str, str, str | None]:
    access = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
    secret = (os.environ.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    token = (os.environ.get("AWS_SESSION_TOKEN") or "").strip() or None
    if not access or not secret:
        raise LlmError(
            "Bedrock requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
            "(optional AWS_SESSION_TOKEN). Or configure an AWS role and export "
            "temporary keys. Region: AWS_REGION / AWS_DEFAULT_REGION."
        )
    return access, secret, token


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret).encode("utf-8"), datestamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def sigv4_headers(
    *,
    method: str,
    url: str,
    body: bytes,
    region: str,
    access_key: str,
    secret_key: str,
    session_token: str | None,
    service: str = "bedrock",
    amz_date: str | None = None,
) -> dict[str, str]:
    """Build SigV4 headers for a Bedrock Runtime request."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    canonical_querystring = parsed.query or ""
    now = datetime.now(UTC)
    amz = amz_date or now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = amz[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    headers_to_sign = {
        "content-type": "application/json",
        "host": host,
        "x-amz-date": amz,
        "x-amz-content-sha256": payload_hash,
    }
    if session_token:
        headers_to_sign["x-amz-security-token"] = session_token
    signed_header_keys = sorted(headers_to_sign)
    canonical_headers = "".join(f"{k}:{headers_to_sign[k]}\n" for k in signed_header_keys)
    signed_headers = ";".join(signed_header_keys)
    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(secret_key, datestamp, region, service),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    out = {
        "Content-Type": "application/json",
        "Host": host,
        "X-Amz-Date": amz,
        "X-Amz-Content-Sha256": payload_hash,
        "Authorization": authorization,
    }
    if session_token:
        out["X-Amz-Security-Token"] = session_token
    return out


def bedrock_converse_stream_url(*, region: str, model_id: str) -> str:
    # Model ids may contain `:` and `/` — encode path segment.
    encoded = quote(model_id, safe=".-_:")
    return (
        f"https://bedrock-runtime.{region}.amazonaws.com"
        f"/model/{encoded}/converse-stream"
    )


def bedrock_converse_payload(prompt: str) -> dict[str, Any]:
    return {
        "system": [{"text": SYSTEM_PROMPT}],
        "messages": [
            {"role": "user", "content": [{"text": prompt}]},
        ],
        "inferenceConfig": {"temperature": 0.1},
    }


def _crc32(data: bytes) -> int:
    import zlib

    return zlib.crc32(data) & 0xFFFFFFFF


def encode_event_stream_message(payload: bytes, *, event_type: str = "chunk") -> bytes:
    """Build one AWS event-stream message (for unit tests)."""
    # Header: :event-type (7) + name + value type 7 (string) + value
    name = b":event-type"
    value = event_type.encode("utf-8")
    header = (
        bytes([len(name)])
        + name
        + bytes([7])  # string
        + struct.pack(">H", len(value))
        + value
    )
    headers_len = len(header)
    # total = prelude(12) + headers + payload + message_crc(4)
    total_len = 12 + headers_len + len(payload) + 4
    prelude = struct.pack(">II", total_len, headers_len)
    prelude_crc = struct.pack(">I", _crc32(prelude))
    message_wo_crc = prelude + prelude_crc + header + payload
    message_crc = struct.pack(">I", _crc32(message_wo_crc))
    return message_wo_crc + message_crc


def iter_event_stream_payloads(blob: bytes) -> Iterator[bytes]:
    """Yield message payloads from an AWS event-stream byte blob."""
    offset = 0
    n = len(blob)
    while offset + 12 <= n:
        total_len, headers_len = struct.unpack_from(">II", blob, offset)
        if total_len < 16 or offset + total_len > n:
            break
        # Skip prelude (8) + prelude crc (4) + headers
        payload_start = offset + 12 + headers_len
        payload_end = offset + total_len - 4  # exclude message crc
        if payload_start > payload_end:
            break
        yield blob[payload_start:payload_end]
        offset += total_len


def _delta_text(node: object) -> str | None:
    if not isinstance(node, dict):
        return None
    text = node.get("text")
    if isinstance(text, str) and text:
        return text
    return None


def extract_text_from_bedrock_payload(payload: bytes) -> str | None:
    """Pull assistant text from a Converse stream event JSON payload."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    text = _delta_text(data.get("delta"))
    if text:
        return text
    block = data.get("contentBlockDelta")
    if isinstance(block, dict):
        return _delta_text(block.get("delta"))
    return None


def iter_bedrock_text_deltas(byte_iter: Iterator[bytes]) -> Iterator[str]:
    """Decode Converse event-stream bytes into text deltas."""
    buffer = b""
    for chunk in byte_iter:
        buffer += chunk
        # Process complete messages greedily.
        while True:
            if len(buffer) < 12:
                break
            total_len, _headers_len = struct.unpack_from(">II", buffer, 0)
            if total_len < 16 or len(buffer) < total_len:
                break
            message = buffer[:total_len]
            buffer = buffer[total_len:]
            for payload in iter_event_stream_payloads(message):
                text = extract_text_from_bedrock_payload(payload)
                if text:
                    yield text


def analyze_bedrock(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    access, secret, session = resolve_aws_credentials()
    region = resolve_bedrock_region()
    model = model_cfg.model or default_model("bedrock") or DEFAULT_BEDROCK_MODEL
    url = bedrock_converse_stream_url(region=region, model_id=model)
    if model_cfg.base_url:
        # Allow test doubles / private endpoints.
        root = model_cfg.base_url.rstrip("/")
        encoded = quote(model, safe=".-_:")
        url = f"{root}/model/{encoded}/converse-stream"
    body_obj = bedrock_converse_payload(prompt)
    body = json.dumps(body_obj, separators=(",", ":")).encode("utf-8")
    headers = sigv4_headers(
        method="POST",
        url=url,
        body=body,
        region=region,
        access_key=access,
        secret_key=secret,
        session_token=session,
        service="bedrock",
    )
    timeout = resolve_llm_timeout(model_cfg)
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    parts: list[str] = []
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        with client.stream("POST", url, headers=headers, content=body) as response:
            if response.status_code >= 400:
                detail = (
                    response.read().decode("utf-8", errors="replace") or ""
                ).strip()
                if len(detail) > 300:
                    detail = detail[:300] + "…"
                raise LlmError(
                    f"Bedrock error {response.status_code}"
                    + (f": {detail}" if detail else "")
                )

            def _byte_chunks() -> Iterator[bytes]:
                for piece in response.iter_bytes():
                    if time.monotonic() >= deadline:
                        raise LlmError(
                            f"Bedrock timed out after {timeout:g}s. "
                            f"Try `--timeout {int(timeout * 2)}`."
                        )
                    yield piece

            for text in iter_bedrock_text_deltas(_byte_chunks()):
                parts.append(text)
                if on_delta is not None:
                    on_delta(text)
    except httpx.TimeoutException as exc:
        raise LlmError(
            f"Bedrock timed out after {timeout:g}s. "
            f"Try `--timeout {int(timeout * 2)}`."
        ) from exc
    finally:
        if owns_client:
            client.close()
    content = "".join(parts)
    if not content.strip():
        raise LlmError("Bedrock stream completed with empty content")
    return content
