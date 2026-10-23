"""Load an instruction file into the prompt slot and the pass cache."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.deep import DeepPass, build_deep_prompt
from repolens.deep_types import coverage_closure_prompt
from repolens.dspy_program import instruction_hashes, program_for_pass
from repolens.inventory import FileEntry
from repolens.pipeline.pass_cache import PassKey, closure_key, pass_key
from repolens.prose import BRITISH_ENGLISH_INSTRUCTION
from repolens.report_sections import _provenance_identity_lines
from repolens.rules.registry import Rule
from repolens.schema import ProvenanceBlock

STOCK = "Analyse using the rules and coverage contract. Return FindingReport JSON only."
TAIL = "Stay with the checklist."
HINT = "Return FindingReport JSON only."


def _pass() -> DeepPass:
    entry = FileEntry(path=Path("a.py"), relative="a.py", size=10, priority_band=1)
    return DeepPass(
        name="p1",
        rule_ids=["sec.injection"],
        coverage_ids=["sec.injection"],
        files=[entry],
    )


def _rule() -> Rule:
    return Rule(
        id="sec.injection",
        band="p1",
        enabled=True,
        title="Injection",
        body="Look for injection.",
    )


def _body(pass_name: str = "p1") -> dict[str, object]:
    return {
        "kind": "repolens.dspy-instruction",
        "version": 1,
        "pass": pass_name,
        "optimizer": "instruction-only",
        "instructionTail": TAIL,
        "formatHint": HINT,
        "demos": [],
    }


def test_omitted_strings_keep_the_stock_prompt() -> None:
    plain = build_deep_prompt(_pass(), [_rule()], ["sec.injection"])
    explicit = build_deep_prompt(
        _pass(),
        [_rule()],
        ["sec.injection"],
        instruction_tail=None,
        format_hint=None,
    )
    assert plain == explicit
    assert plain.endswith(STOCK)


def test_loaded_strings_replace_only_the_format_sentence() -> None:
    loaded = build_deep_prompt(
        _pass(),
        [_rule()],
        ["sec.injection"],
        instruction_tail=TAIL,
        format_hint=HINT,
    )
    assert STOCK not in loaded
    assert loaded.index(BRITISH_ENGLISH_INSTRUCTION) < loaded.index(TAIL) < loaded.index(HINT)


def test_closure_prompt_replaces_only_the_json_sentence() -> None:
    stock = coverage_closure_prompt(["sec.injection"])
    loaded = coverage_closure_prompt(
        ["sec.injection"],
        instruction_tail=TAIL,
        format_hint=HINT,
    )
    assert "Return FindingReport JSON only." in stock
    assert BRITISH_ENGLISH_INSTRUCTION in loaded
    assert TAIL in loaded and HINT in loaded
    assert "Return FindingReport JSON only." not in loaded.replace(HINT, "")


def test_stock_cache_key_ignores_a_missing_instruction_hash(tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("print(1)\n", encoding="utf-8")
    entry = FileEntry(path=path, relative="a.py", size=path.stat().st_size, priority_band=1)
    bare = pass_key(PassKey(files=[entry], model="qwen", pass_name="p1"))
    explicit = pass_key(
        PassKey(files=[entry], model="qwen", pass_name="p1", instruction_hash=None)
    )
    hashed = pass_key(
        PassKey(files=[entry], model="qwen", pass_name="p1", instruction_hash="aaa")
    )
    again = pass_key(
        PassKey(files=[entry], model="qwen", pass_name="p1", instruction_hash="bbb")
    )
    assert bare == explicit
    assert hashed != bare
    assert again != hashed
    assert closure_key(["sec.injection"], "qwen") == closure_key(
        ["sec.injection"], "qwen", instruction_hash=None
    )
    assert closure_key(["sec.injection"], "qwen", instruction_hash="aaa") != closure_key(
        ["sec.injection"], "qwen"
    )


def test_directory_loads_only_the_matching_pass(tmp_path: Path) -> None:
    (tmp_path / "p1.json").write_text(json.dumps(_body("p1")), encoding="utf-8")
    p1 = program_for_pass(str(tmp_path), tmp_path, "p1")
    p2 = program_for_pass(str(tmp_path), tmp_path, "p2")
    assert p1.tail == TAIL and p1.hint == HINT and p1.cache_hash
    assert p2.tail is None and p2.provenance is None
    hashes = instruction_hashes(str(tmp_path), tmp_path)
    assert list(hashes) == ["p1"]


def test_single_file_applies_only_to_its_pass(tmp_path: Path) -> None:
    path = tmp_path / "one.json"
    path.write_text(json.dumps(_body("p1"), indent=4), encoding="utf-8")
    compact = tmp_path / "flat.json"
    compact.write_text(json.dumps(_body("p1"), separators=(",", ":")), encoding="utf-8")
    pretty = program_for_pass(str(path), tmp_path, "p1")
    flat = program_for_pass(str(compact), tmp_path, "p1")
    other = program_for_pass(str(path), tmp_path, "p2")
    assert pretty.cache_hash == flat.cache_hash
    assert other.provenance is None


def test_invalid_file_is_rejected_and_keeps_the_stock_cache_key(tmp_path: Path) -> None:
    path = tmp_path / "p1.json"
    path.write_text("{", encoding="utf-8")
    loaded = program_for_pass(str(tmp_path), tmp_path, "p1")
    assert loaded.cache_hash is None
    assert loaded.provenance == "rejected"
    lines = _provenance_identity_lines(ProvenanceBlock(dspyInstructionHash={"p1": "rejected"}))
    assert any("p1" in line and "rejected" in line for line in lines)
