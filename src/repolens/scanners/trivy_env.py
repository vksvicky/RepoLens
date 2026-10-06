"""Trivy subprocess environment allowlist and secret redaction (#94)."""

from __future__ import annotations

from collections.abc import Mapping

ALLOWLIST = (
    "TRIVY_USERNAME",
    "TRIVY_PASSWORD",
    "TRIVY_REGISTRY_TOKEN",
    "TRIVY_AUTH_URL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_PROFILE",
    "AWS_REGION",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    "AZURE_TENANT_ID",
    "AZURE_FEDERATED_TOKEN_FILE",
)

INCOMPLETE_AUTH_DETAIL = (
    "registry auth incomplete (username without password or token)"
)


def _stripped(environ: Mapping[str, str], key: str) -> str:
    return (environ.get(key) or "").strip()


def registry_auth_incomplete(environ: Mapping[str, str]) -> bool:
    user = _stripped(environ, "TRIVY_USERNAME")
    if not user:
        return False
    password = _stripped(environ, "TRIVY_PASSWORD")
    token = _stripped(environ, "TRIVY_REGISTRY_TOKEN")
    return not password and not token


def trivy_child_env(
    environ: Mapping[str, str], *, pass_registry_env: bool
) -> dict[str, str]:
    env = {str(k): str(v) for k, v in environ.items() if v is not None}
    if not pass_registry_env:
        for key in ALLOWLIST:
            env.pop(key, None)
        return env
    for key in ALLOWLIST:
        value = _stripped(environ, key)
        if value:
            env[key] = value
        else:
            env.pop(key, None)
    return env


def redact_secrets(text: str, environ: Mapping[str, str]) -> str:
    redacted = text
    for key in ALLOWLIST:
        secret = _stripped(environ, key)
        if len(secret) < 3:
            continue
        redacted = redacted.replace(secret, "***")
    return redacted
