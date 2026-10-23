#!/usr/bin/env python3
"""Write a Slow Brain instruction file. This script is not part of a review.

Install the compiler by hand when you want a live run. It is not a package dependency:

    pip install dspy

One live compile is an offline job on the reference local model, ``qwen2.5-coder:32b``.
``repolens review`` does not import this file and does not import DSPy.
The only optimizer name this script accepts is ``instruction-only``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from repolens.dspy_program import ProgramRejected, parse_program  # noqa: E402

_ALLOWED_OPTIMIZER = "instruction-only"
_FIXTURE_PARTS = ("tests", "fixtures", "dspy")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a DSPy instruction tail.")
    parser.add_argument("--pass-name", required=True, choices=["p1", "p2", "p3", "coverage"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tail", required=True)
    parser.add_argument("--hint", required=True)
    parser.add_argument("--optimizer", default=_ALLOWED_OPTIMIZER)
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args(argv)
    require_optimizer(args.optimizer)
    if args.fixture is not None:
        require_fixture(args.fixture, Path(__file__).resolve().parents[1])
    write_instruction(args.out, args.pass_name, args.tail, args.hint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
