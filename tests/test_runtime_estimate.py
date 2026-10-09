"""Pre-flight Slow Brain wall-time estimate (#15)."""

from __future__ import annotations

from repolens.runtime_estimate import estimate_deep_runtime, estimate_deep_runtime_minutes


def test_estimate_ollama_32b_band_is_hours_for_large_pack() -> None:
    text = estimate_deep_runtime(files=200, passes=3, provider="ollama")
    assert "Slow Brain estimate" in text
    assert "200" in text
    assert "3" in text
    minutes = estimate_deep_runtime_minutes(files=200, passes=3, provider="ollama")
    assert minutes >= 60


def test_estimate_deep_passes_one_is_roughly_one_third() -> None:
    full = estimate_deep_runtime_minutes(files=90, passes=3, provider="ollama")
    one = estimate_deep_runtime_minutes(files=90, passes=1, provider="ollama")
    assert one < full
    assert one * 2.5 <= full <= one * 3.5


def test_estimate_cloud_provider_faster_than_local() -> None:
    local = estimate_deep_runtime_minutes(files=100, passes=2, provider="ollama")
    cloud = estimate_deep_runtime_minutes(files=100, passes=2, provider="openai")
    assert cloud < local


def test_estimate_zero_files_or_passes() -> None:
    assert estimate_deep_runtime_minutes(files=0, passes=3, provider="ollama") == 0
    text = estimate_deep_runtime(files=0, passes=1, provider="ollama")
    assert "no LLM files" in text.lower() or "0" in text


def test_estimate_line_names_byok_vs_airgap_class() -> None:
    ollama = estimate_deep_runtime(files=10, passes=1, provider="ollama")
    assert "air-gap" in ollama.lower()
    cloud = estimate_deep_runtime(files=10, passes=1, provider="openai")
    assert "byok" in cloud.lower()
