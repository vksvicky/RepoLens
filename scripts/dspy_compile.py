#!/usr/bin/env python3
"""Compile a Slow Brain instruction file. This script is not part of a review.

Install the compiler by hand for a live run. It is not a package dependency:

    pip install dspy

One live compile is an offline job on the reference local model, ``qwen2.5-coder:32b``.
The live path calls DSPy ``COPRO``, which tunes the instruction and the format hint
and does not store demos. ``repolens review`` does not import this file and does not
import DSPy. The only optimizer name this script accepts is ``instruction-only``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from repolens.config import ModelConfig, load_config, resolve_api_key  # noqa: E402
from repolens.dspy_program import ProgramRejected, parse_program, score_report  # noqa: E402
from repolens.providers import default_base_url_for, default_model_for  # noqa: E402

_ALLOWED_OPTIMIZER = "instruction-only"
_FIXTURE_PARTS = ("tests", "fixtures", "dspy")
_REFERENCE_MODEL = "qwen2.5-coder:32b"
_MAX_FIXTURE_FILES = 10
_COPRO_BREADTH = 4
_COPRO_DEPTH = 2
_LOCAL_KEY = "ollama"
_LM_PREFIX = {
    "ollama": "openai",
    "openai_compatible": "openai",
    "openai": "openai",
    "anthropic": "anthropic",
    "deepseek": "deepseek",
    "gemini": "gemini",
}


@dataclass(frozen=True)
class CompileTarget:
    """The one model endpoint a compile is allowed to call."""

    provider: str
    model: str
    base_url: str
    api_key: str


def write_instruction(
    path: Path,
    pass_name: str,
    instruction_tail: str,
    format_hint: str,
) -> None:
    """Write one instruction file and read it back through the review validator."""
    body = {
        "kind": "repolens.dspy-instruction",
        "version": 1,
        "pass": pass_name,
        "optimizer": _ALLOWED_OPTIMIZER,
        "instructionTail": instruction_tail,
        "formatHint": format_hint,
        "demos": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    try:
        parse_program(json.loads(path.read_text(encoding="utf-8")))
    except ProgramRejected as exc:
        path.unlink(missing_ok=True)
        raise SystemExit(str(exc)) from exc


def require_optimizer(name: str) -> None:
    """Refuse any optimizer that can store demos."""
    if name != _ALLOWED_OPTIMIZER:
        raise SystemExit(f"optimizer {name} is not allowed; use {_ALLOWED_OPTIMIZER}")


def require_fixture(path: Path, repo: Path) -> Path:
    """A compile may read only the synthetic trees under tests/fixtures/dspy."""
    root = repo.joinpath(*_FIXTURE_PARTS).resolve()
    chosen = path.resolve()
    try:
        chosen.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"compile only reads {root}") from exc
    return chosen


def compile_target(model: ModelConfig) -> CompileTarget:
    """Resolve every provider through the same four fields."""
    provider = model.provider or "ollama"
    name = model.model or _default_model(provider)
    base = model.base_url.rstrip("/") if model.base_url else _base_for(provider)
    key = resolve_api_key(model) or _LOCAL_KEY
    return CompileTarget(provider, name, base, key)


def metric_score(candidate: str, manifest: dict) -> float:
    """The float in ``[0, 1]`` that the optimizer's metric returns."""
    return score_report(candidate, manifest).total


def fixture_sources(path: Path) -> list[Path]:
    """Source files for one scenario. The manifest is not a trial input."""
    files = sorted(
        item for item in path.rglob("*") if item.is_file() and item.name != "manifest.json"
    )
    if len(files) > _MAX_FIXTURE_FILES:
        raise SystemExit(f"a compile fixture has at most {_MAX_FIXTURE_FILES} files")
    return files


def compile_instruction(
    fixture: Path,
    pass_name: str,
    target: CompileTarget,
    optimize,
) -> tuple[str, str]:
    """Print the model, then ask the optimizer for the two strings."""
    print(f"{target.provider} {target.model}", file=sys.stderr)
    return optimize(fixture, pass_name, target)


def instruction_only_optimize(
    fixture: Path,
    pass_name: str,
    target: CompileTarget,
) -> tuple[str, str]:
    """Tune the two strings with COPRO. Trial excerpts are not written out."""
    dspy = _import_dspy()
    sources = fixture_sources(fixture)
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    lm = _language_model(dspy, target)
    compiled = _run_copro(dspy, _student(dspy), _trainset(dspy, sources, manifest, pass_name), lm)
    return _compiled_strings(compiled)


def main(argv: list[str] | None = None, *, optimize=None) -> int:
    parser = argparse.ArgumentParser(description="Write a DSPy instruction tail.")
    parser.add_argument("--pass-name", required=True, choices=["p1", "p2", "p3", "coverage"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tail")
    parser.add_argument("--hint")
    parser.add_argument("--optimizer", default=_ALLOWED_OPTIMIZER)
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args(argv)
    require_optimizer(args.optimizer)
    if args.tail is not None or args.hint is not None:
        _write_supplied(args)
        return 0
    if args.fixture is None:
        raise SystemExit("a live compile needs --fixture")
    repo = Path(__file__).resolve().parents[1]
    fixture = require_fixture(args.fixture, repo)
    target = compile_target(load_config(None).model)
    tail, hint = compile_instruction(
        fixture,
        args.pass_name,
        target,
        optimize or instruction_only_optimize,
    )
    write_instruction(args.out, args.pass_name, tail, hint)
    return 0


def _write_supplied(args: argparse.Namespace) -> None:
    if not args.tail or not args.hint:
        raise SystemExit("pass both --tail and --hint, or neither")
    write_instruction(args.out, args.pass_name, args.tail, args.hint)


def _default_model(provider: str) -> str:
    if provider == "ollama":
        return _REFERENCE_MODEL
    return default_model_for(provider) or _REFERENCE_MODEL


def _base_for(provider: str) -> str:
    if provider == "ollama":
        return _ollama_base()
    return default_base_url_for(provider).rstrip("/")


def _ollama_base() -> str:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip().rstrip("/")
    if host.endswith("/v1"):
        return host
    return f"{host}/v1"


def _import_dspy():
    try:
        import dspy
    except ImportError as exc:
        raise SystemExit("pip install dspy") from exc
    return dspy


def _language_model(dspy, target: CompileTarget):
    return dspy.LM(
        _model_id(target),
        api_base=target.base_url,
        api_key=target.api_key,
        cache=False,
    )


def _model_id(target: CompileTarget) -> str:
    if "/" in target.model:
        return target.model
    return f"{_LM_PREFIX.get(target.provider, 'openai')}/{target.model}"


def _student(dspy):
    class Review(dspy.Signature):
        """Analyse using the rules and coverage contract."""

        source: str = dspy.InputField()
        report: str = dspy.OutputField(desc="Return FindingReport JSON only.")

    return dspy.Predict(Review)


def _trainset(dspy, sources: list[Path], manifest: dict, pass_name: str) -> list:
    body = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
    text = f"Pass {pass_name}\n\n{body}"
    return [dspy.Example(source=text, manifest=manifest).with_inputs("source")]


def _run_copro(dspy, student, trainset: list, lm):
    optimizer = dspy.COPRO(
        prompt_model=lm,
        metric=_copro_metric,
        breadth=_COPRO_BREADTH,
        depth=_COPRO_DEPTH,
    )
    with dspy.context(lm=lm):
        return optimizer.compile(
            student,
            trainset=trainset,
            eval_kwargs={"display_progress": False, "display_table": False},
        )


def _copro_metric(example, prediction, trace=None) -> float:
    del trace
    report = getattr(prediction, "report", "")
    manifest = getattr(example, "manifest", {})
    if not isinstance(manifest, dict):
        return 0.0
    return metric_score(str(report), manifest)


def _compiled_strings(program) -> tuple[str, str]:
    predictors = list(program.predictors())
    if any(getattr(item, "demos", None) for item in predictors):
        raise SystemExit("instruction-only compile stored demos")
    signature = predictors[0].signature
    hint = _output_hint(signature)
    return str(signature.instructions).strip(), hint


def _output_hint(signature) -> str:
    fields = list(signature.output_fields.values())
    if not fields:
        return "Return FindingReport JSON only."
    field = fields[0]
    extra = getattr(field, "json_schema_extra", None) or {}
    prefix = extra.get("prefix") if isinstance(extra, dict) else None
    desc = getattr(field, "desc", None)
    return str(prefix or desc or "Return FindingReport JSON only.").strip()


if __name__ == "__main__":
    raise SystemExit(main())
