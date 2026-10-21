"""Streaming usage is captured for every provider and summed across one repair."""

from __future__ import annotations

import json

from repolens.config import ModelConfig
from repolens.llm.transport import _build_openai_request
from repolens.llm.usage import (
    LlmUsage,
    RawCompletion,
    add_usage,
    fold_usage,
    usage_from_anthropic_event,
    usage_from_bedrock_payload,
    usage_from_gemini_payload,
    usage_from_openai_payload,
)
from repolens.llm_structured import StructuredLlmResult, analyze_structured


def test_add_usage_sums_the_repair_and_refuses_a_missing_side() -> None:
    first = LlmUsage(prompt_tokens=25_000, completion_tokens=1_200, total_tokens=26_200)
    repair = LlmUsage(prompt_tokens=2_000, completion_tokens=1_100, total_tokens=3_100)
    total = add_usage(first, repair)
    assert total == LlmUsage(prompt_tokens=27_000, completion_tokens=2_300, total_tokens=29_300)
    assert add_usage(None, first) is None
    assert add_usage(first, None) is None


def test_openai_stream_asks_for_usage_and_keeps_an_empty_choices_chunk() -> None:
    _base, _model, _headers, payload, use_stream = _build_openai_request(
        "prompt",
        ModelConfig(provider="ollama", model="qwen2.5-coder:32b"),
        None,
        None,
    )
    assert use_stream is True
    assert payload["stream_options"] == {"include_usage": True}
    usage = usage_from_openai_payload(
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}}
    )
    assert usage == LlmUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14)


def test_anthropic_splits_input_and_output_across_events() -> None:
    start = usage_from_anthropic_event(
        {"type": "message_start", "message": {"usage": {"input_tokens": 25, "output_tokens": 1}}}
    )
    delta = usage_from_anthropic_event(
        {"type": "message_delta", "usage": {"output_tokens": 9}}
    )
    folded = fold_usage(start, delta)
    assert folded == LlmUsage(prompt_tokens=25, completion_tokens=9, total_tokens=None)


def test_gemini_usage_metadata_without_text_is_kept() -> None:
    usage = usage_from_gemini_payload(
        {"usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 3, "totalTokenCount": 11}}
    )
    assert usage == LlmUsage(prompt_tokens=8, completion_tokens=3, total_tokens=11)


def test_bedrock_metadata_event_fills_input_and_output() -> None:
    payload = json.dumps(
        {"metadata": {"usage": {"inputTokens": 12, "outputTokens": 5, "totalTokens": 17}}}
    ).encode()
    assert usage_from_bedrock_payload(payload) == LlmUsage(
        prompt_tokens=12, completion_tokens=5, total_tokens=17
    )


def test_repair_usage_is_added_and_a_clean_pass_records_zero_repair(monkeypatch) -> None:
    calls = [
        RawCompletion(
            "not json",
            LlmUsage(prompt_tokens=25_000, completion_tokens=1_200, total_tokens=26_200),
        ),
        RawCompletion(
            json.dumps(
                {
                    "confidence": 100,
                    "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                    "issues": [],
                    "durabilityGaps": [],
                }
            ),
            LlmUsage(prompt_tokens=2_000, completion_tokens=1_100, total_tokens=3_100),
        ),
    ]

    def _fake(prompt, model_cfg, *, client=None, on_delta=None):
        return calls.pop(0)

    monkeypatch.setattr("repolens.llm_structured.analyze_raw", _fake)
    result = analyze_structured("prompt", ModelConfig(provider="ollama"), pass_id="p1")
    assert result.layer == "micro_repair"
    assert result.usage == LlmUsage(
        prompt_tokens=27_000, completion_tokens=2_300, total_tokens=29_300
    )
    assert result.repair_prompt_tokens == 2_000
    assert result.repair_completion_tokens == 1_100
    assert result.repair_attempts == 1

    def _clean(prompt, model_cfg, *, client=None, on_delta=None):
        return RawCompletion(
            json.dumps(
                {
                    "confidence": 90,
                    "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                    "issues": [],
                    "durabilityGaps": [],
                }
            ),
            LlmUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
        )

    monkeypatch.setattr("repolens.llm_structured.analyze_raw", _clean)
    clean = analyze_structured("prompt", ModelConfig(provider="ollama"), pass_id="p1")
    assert clean.usage == LlmUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)
    assert clean.repair_prompt_tokens == 0
    assert clean.repair_completion_tokens == 0
    assert clean.repair_attempts == 0
    assert isinstance(clean, StructuredLlmResult)
