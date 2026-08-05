"""British English prompt conventions."""

from __future__ import annotations

from pathlib import Path

from repolens.deep import DeepPass, build_deep_prompt
from repolens.inventory import FileEntry
from repolens.pipeline import build_prompt
from repolens.prose import BRITISH_ENGLISH_INSTRUCTION
from repolens.rules.registry import Rule


def test_british_english_instruction_mentions_behaviour() -> None:
    assert "British English" in BRITISH_ENGLISH_INSTRUCTION
    assert "behaviour" in BRITISH_ENGLISH_INSTRUCTION


def test_build_prompt_includes_british_english(tmp_path: Path) -> None:
    f = tmp_path / "a.py"
    f.write_text("print(1)\n", encoding="utf-8")
    entry = FileEntry(
        path=f,
        relative="a.py",
        size=f.stat().st_size,
        priority_band=3,
    )
    prompt = build_prompt("review", tmp_path, [entry], full_audit=False)
    assert BRITISH_ENGLISH_INSTRUCTION in prompt
    assert "Analyse the files" in prompt


def test_deep_prompt_includes_british_english() -> None:
    entry = FileEntry(
        path=Path("a.py"),
        relative="a.py",
        size=10,
        priority_band=1,
    )
    rule = Rule(
        id="sec.injection",
        band="p1",
        enabled=True,
        title="Injection",
        body="Look for injection.",
    )
    deep_pass = DeepPass(
        name="p1",
        rule_ids=["sec.injection"],
        coverage_ids=["sec.injection"],
        files=[entry],
    )
    prompt = build_deep_prompt(
        deep_pass,
        rules=[rule],
        coverage_ids=["sec.injection"],
    )
    assert BRITISH_ENGLISH_INSTRUCTION in prompt
    assert "Analyse using the rules" in prompt
