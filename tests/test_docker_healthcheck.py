"""The published image declares a HEALTHCHECK."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_runtime_stage_has_healthcheck() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = text.split("FROM python:${PYTHON_VERSION}-slim-bookworm")[-1]
    assert "HEALTHCHECK" in runtime
    assert "repolens version" in runtime
