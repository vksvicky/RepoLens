"""The maintainer script writes an instruction file. Tests never call a live model."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from repolens.config import ModelConfig
from repolens.dspy_program import instruction_digest, parse_program, score_report

_SCRIPT = Path("scripts/dspy_compile.py")
_TAIL = "Stay with the checklist."
_HINT = "Return FindingReport JSON only."


def _compiler():
    spec = importlib.util.spec_from_file_location("dspy_compile", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dspy_compile"] = module
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
    assert program.digest == instruction_digest("p1", _TAIL, _HINT)
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


def test_loading_the_script_does_not_import_dspy() -> None:
    sys.modules.pop("dspy", None)
    _compiler()
    assert "dspy" not in sys.modules


def test_package_does_not_depend_on_dspy() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "dspy" not in text


def test_unset_model_uses_the_local_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    target = _compiler().compile_target(ModelConfig())
    assert target.provider == "ollama"
    assert target.model == "qwen2.5-coder:32b"
    assert target.base_url == "http://127.0.0.1:11434/v1"
    assert target.api_key == "ollama"


def test_ollama_host_sets_the_local_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11435/")
    target = _compiler().compile_target(ModelConfig(provider="ollama"))
    assert target.base_url == "http://127.0.0.1:11435/v1"


def test_configured_base_url_wins_over_ollama_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11435")
    target = _compiler().compile_target(
        ModelConfig(provider="ollama", model="other:7b", base_url="http://127.0.0.1:9/v1")
    )
    assert target.model == "other:7b"
    assert target.base_url == "http://127.0.0.1:9/v1"


def test_cloud_uses_the_same_endpoint_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11435")
    target = _compiler().compile_target(ModelConfig(provider="openai"))
    assert target.provider == "openai"
    assert target.model == "gpt-4.1-mini"
    assert target.base_url == "https://api.openai.com/v1"


def test_metric_score_is_the_report_total() -> None:
    manifest = {"ids": [], "expected": []}
    score = _compiler().metric_score("not-json", manifest)
    assert score == score_report("not-json", manifest).total


def test_fixture_dir_stops_at_ten_files(tmp_path: Path) -> None:
    for index in range(11):
        (tmp_path / f"n{index}.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _compiler().fixture_sources(tmp_path)


def test_supplied_strings_do_not_call_the_optimizer(tmp_path: Path) -> None:
    called: list[object] = []
    code = _compiler().main(
        [
            "--pass-name",
            "p1",
            "--out",
            str(tmp_path / "p1.json"),
            "--tail",
            _TAIL,
            "--hint",
            _HINT,
        ],
        optimize=lambda *_args: called.append(_args),
    )
    assert code == 0
    assert called == []


def test_live_compile_announces_the_model_before_the_call(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiler = _compiler()
    monkeypatch.setattr(
        compiler,
        "load_config",
        lambda *_args, **_kwargs: SimpleNamespace(model=ModelConfig()),
    )
    seen: list[object] = []

    def optimize(fixture: Path, pass_name: str, target: object) -> tuple[str, str]:
        seen.append(capsys.readouterr().err.strip())
        seen.append((fixture.name, pass_name, target.model))
        return _TAIL, _HINT

    code = compiler.main(
        [
            "--pass-name",
            "p1",
            "--out",
            str(tmp_path / "p1.json"),
            "--fixture",
            "tests/fixtures/dspy/swallow",
        ],
        optimize=optimize,
    )
    program = parse_program(json.loads((tmp_path / "p1.json").read_text(encoding="utf-8")))
    assert code == 0
    assert seen == ["ollama qwen2.5-coder:32b", ("swallow", "p1", "qwen2.5-coder:32b")]
    assert program.digest == instruction_digest("p1", _TAIL, _HINT)
    saved = json.loads((tmp_path / "p1.json").read_text(encoding="utf-8"))
    assert saved["demos"] == []


def test_live_optimizer_asks_for_dspy_when_it_is_missing() -> None:
    compiler = _compiler()
    target = compiler.compile_target(ModelConfig())
    sys.modules["dspy"] = None
    try:
        with pytest.raises(SystemExit, match="pip install dspy"):
            compiler.instruction_only_optimize(
                Path("tests/fixtures/dspy/swallow"),
                "p1",
                target,
            )
    finally:
        sys.modules.pop("dspy", None)


def test_compiled_strings_keep_the_instruction_and_refuse_demos() -> None:
    compiler = _compiler()
    field = SimpleNamespace(desc=_HINT, json_schema_extra={"prefix": _HINT})
    signature = SimpleNamespace(instructions=_TAIL, output_fields={"report": field})
    clean = SimpleNamespace(predictors=lambda: [SimpleNamespace(signature=signature, demos=[])])
    assert compiler._compiled_strings(clean) == (_TAIL, _HINT)
    stored = SimpleNamespace(
        predictors=lambda: [SimpleNamespace(signature=signature, demos=[{"source": "x"}])]
    )
    with pytest.raises(SystemExit, match="demos"):
        compiler._compiled_strings(stored)


def test_model_id_uses_one_openai_compatible_prefix() -> None:
    compiler = _compiler()
    local = compiler.compile_target(ModelConfig(provider="ollama", model="qwen2.5-coder:32b"))
    cloud = compiler.compile_target(ModelConfig(provider="openai", model="gpt-4.1-mini"))
    assert compiler._model_id(local) == "openai/qwen2.5-coder:32b"
    assert compiler._model_id(cloud) == "openai/gpt-4.1-mini"


def test_one_string_without_the_other_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        _compiler().main(
            ["--pass-name", "p1", "--out", str(tmp_path / "p1.json"), "--tail", _TAIL]
        )
