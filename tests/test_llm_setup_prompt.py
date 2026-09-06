from repolens.llm.parse import repair_prompt
from repolens.llm.setup import SYSTEM_PROMPT


def test_system_prompt_explains_empty_pack_confidence() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "issues" in text and "confidence" in text
    assert "free of" in text or "no issues" in text
    assert "empty" in text


def test_repair_prompt_mentions_empty_pack_confidence() -> None:
    msg = repair_prompt("orig", "boom").lower()
    assert "confidence" in msg
    assert "empty" in msg or "no issues" in msg or "free of" in msg
