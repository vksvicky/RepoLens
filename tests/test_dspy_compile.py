"""The maintainer script writes an instruction file. It does not call a model."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from repolens.dspy_program import parse_program

_SCRIPT = Path("scripts/dspy_compile.py")


def _compiler():
    spec = importlib.util.spec_from_file_location("dspy_compile", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_writer_round_trips_a_fake_optimizer_result(tmp_path: Path) -> None:
    compiler = _compiler()
    out = tmp_path / "p1.json"
    compiler.write_instruction(
        out,
        "p1",
        "Stay with the checklist.",
        "Return FindingReport JSON only.",
    )
    program = parse_program(json.loads(out.read_text(encoding="utf-8")))
    assert program.pass_name == "p1"
    assert program.digest
    assert json.loads(out.read_text(encoding="utf-8"))["demos"] == []


def test_writer_rejects_a_fixture_citation(tmp_path: Path) -> None:
    compiler = _compiler()
    with pytest.raises(SystemExit):
        compiler.write_instruction(
            tmp_path / "p1.json",
            "p1",
            "see tests/fixtures/dspy/secret",
            "Return FindingReport JSON only.",
        )
    assert not (tmp_path / "p1.json").exists()


def test_optimizer_and_fixture_guards(tmp_path: Path) -> None:
    compiler = _compiler()
    with pytest.raises(SystemExit):
        compiler.require_optimizer("BootstrapFewShot")
    with pytest.raises(SystemExit):
        compiler.require_fixture(tmp_path, Path("."))
    allowed = compiler.require_fixture(Path("tests/fixtures/dspy/secret"), Path("."))
    assert allowed.name == "secret"
