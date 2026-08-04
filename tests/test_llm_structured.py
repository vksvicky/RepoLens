import json

import pytest

from repolens.config import ModelConfig
from repolens.llm import LlmError
from repolens.llm_structured import analyze_structured


@pytest.fixture
def mock_analyze_raw(monkeypatch):
    responses = []
    
    def _mock(prompt, model_cfg, *, client=None):
        if not responses:
            raise LlmError("No more mock responses")
        res = responses.pop(0)
        if isinstance(res, Exception):
            raise res
        return res
    
    monkeypatch.setattr("repolens.llm_structured.analyze_raw", _mock)
    return responses


def test_coerce_success(mock_analyze_raw):
    # Valid JSON but needs coercion (confidence as string, weird severity)
    raw = json.dumps({
        "confidence": "95%",
        "summary": {"critical": 0, "high": "1", "medium": 0, "low": 0},
        "issues": [
            {
                "severity": "CRIT", 
                "priority": "1", 
                "title": "Test", 
                "explanation": "Oops",
                "impact": "bad",
                "codeExample": "foo"
            }
        ],
        "durabilityGaps": "Just a string gap"
    })
    mock_analyze_raw.append(raw)
    
    cfg = ModelConfig(provider="openai_compatible", api_key="dummy")
    result = analyze_structured("test prompt", cfg, pass_id="pass_2")
    
    assert result.layer == "coerced"
    assert result.report is not None
    assert result.report.confidence == 95
    assert result.report.issues[0].severity.value == "CRITICAL"
    assert result.report.issues[0].priority == "P1"
    assert result.report.durabilityGaps == ["Just a string gap"]


def test_uncoerceable_json_micro_repair_success(mock_analyze_raw):
    # First response: completely invalid JSON structure that cannot be coerced (e.g. just text)
    mock_analyze_raw.append("Hello world this is not json")
    
    # Second response (micro-repair): valid JSON
    valid_json = json.dumps({
        "confidence": 100,
        "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "issues": [],
        "durabilityGaps": []
    })
    mock_analyze_raw.append(valid_json)
    
    cfg = ModelConfig(provider="openai_compatible", api_key="dummy")
    result = analyze_structured("test prompt", cfg, pass_id="pass_3")
    
    assert result.layer == "micro_repair"
    assert result.report is not None
    assert result.report.confidence == 100


def test_micro_repair_fails_degrades(mock_analyze_raw, tmp_path, monkeypatch):
    # Both fail
    mock_analyze_raw.append("First bad response")
    mock_analyze_raw.append("Second bad response")
    
    # Point .repolens to a tmp directory to test file saving
    monkeypatch.chdir(tmp_path)
    
    cfg = ModelConfig(provider="openai_compatible", api_key="dummy")
    result = analyze_structured("test prompt", cfg, pass_id="pass_4")
    
    assert result.layer == "degraded"
    assert result.error is not None
    assert result.report is not None
    # We should get an empty report with a durability gap
    assert len(result.report.durabilityGaps) == 1
    assert "llm.schema_invalid" in result.report.durabilityGaps[0]
    
    # Check if raw text was saved
    saved_file = tmp_path / ".repolens" / "last_llm_raw_pass_4.txt"
    assert saved_file.exists()
    assert saved_file.read_text() == "Second bad response"


def test_network_failure_degrades_immediately(mock_analyze_raw, tmp_path, monkeypatch):
    mock_analyze_raw.append(LlmError("Timeout!"))
    monkeypatch.chdir(tmp_path)
    
    cfg = ModelConfig(provider="openai_compatible", api_key="dummy")
    result = analyze_structured("test prompt", cfg, pass_id="pass_net")
    
    assert result.layer == "degraded"
    assert "Timeout!" in result.error
    assert len(result.report.durabilityGaps) == 1
    assert "llm.schema_invalid" in result.report.durabilityGaps[0]
