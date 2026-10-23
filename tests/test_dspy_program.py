"""Parser, validator, and metric for a DSPy instruction file. No model call."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from repolens.dspy_program import (
    ProgramRejected,
    instruction_digest,
    parse_program,
    score_report,
)
from repolens.schema import FindingReport, Issue, Severity, Summary

FIXTURE = Path("tests/fixtures/dspy/secret")
TAIL = "Name the secret finding. Do not quote the fixture."
HINT = "Return FindingReport JSON only."


def _program(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "kind": "repolens.dspy-instruction",
        "version": 1,
        "pass": "p1",
        "optimizer": "instruction-only",
        "instructionTail": TAIL,
        "formatHint": HINT,
        "demos": [],
    }
    body.update(overrides)
    return body


def _issue(*, line: int = 1, category: str = "sec.repo_hygiene_secrets") -> Issue:
    return Issue(
        severity=Severity.HIGH,
        priority="P1",
        category=category,
        file="app.py",
        line=line,
        title="Hardcoded token",
        explanation="A token is assigned in source.",
        impact="Anyone with the file can reuse the token.",
        recommendedFix="Read the token from the environment.",
        codeExample="TOKEN = os.environ['TOKEN']",
    )


def _report(
    manifest: dict[str, object],
    *,
    line: int = 1,
    extra_gaps: list[str] | None = None,
) -> FindingReport:
    gaps = [
        f"coverage:{cid}: N/A — {reason}"
        for cid, reason in dict(manifest["na"]).items()
    ]
    if extra_gaps:
        gaps.extend(extra_gaps)
    return FindingReport(
        confidence=80,
        summary=Summary(high=1),
        issues=[_issue(line=line)],
        durabilityGaps=gaps,
    )


def test_accepts_a_fenced_json_format_hint() -> None:
    hint = '```json\n{"schemaVersion": "1.0"}\n```'
    program = parse_program(_program(formatHint=hint))
    assert program.format_hint == hint
    assert program.pass_name == "p1"


def test_digest_ignores_key_order_and_matches_the_nul_join() -> None:
    first = parse_program(json.loads(json.dumps(_program(), indent=2)))
    second = parse_program(
        {
            "demos": [],
            "formatHint": HINT,
            "instructionTail": TAIL,
            "optimizer": "instruction-only",
            "pass": "p1",
            "version": 1,
            "kind": "repolens.dspy-instruction",
        }
    )
    expect = hashlib.sha256(f"p1\0{TAIL}\0{HINT}".encode()).hexdigest()
    assert first.digest == second.digest == expect == instruction_digest("p1", TAIL, HINT)


def test_a_different_tail_changes_the_digest() -> None:
    original = parse_program(_program()).digest
    changed = parse_program(_program(instructionTail=TAIL + " Stay specific.")).digest
    assert original != changed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("demos", ["one"]),
        ("instructionTail", "see tests/fixtures/dspy/secret"),
        ("instructionTail", "open secret.py"),
        ("instructionTail", "see line 12"),
        ("formatHint", "a" * 1001),
        ("instructionTail", "b" * 2001),
        ("examples", []),
        ("fewshot", []),
        ("demonstrations", []),
        ("pass", "p4"),
    ],
)
def test_rejects_unsafe_or_oversized_programs(field: str, value: object) -> None:
    with pytest.raises(ProgramRejected):
        parse_program(_program(**{field: value}))


def test_accepts_the_character_caps() -> None:
    program = parse_program(_program(formatHint="a" * 1000, instructionTail="b" * 2000))
    assert len(program.format_hint) == 1000
    assert len(program.instruction_tail) == 2000


def test_secret_manifest_scores_one_when_the_report_matches() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    source = (FIXTURE / "app.py").read_text().splitlines()
    assert source[0] == 'TOKEN = "fixture-token"'
    parts = score_report(_report(manifest).model_dump_json(), manifest)
    assert parts.schema == 0.25
    assert parts.coverage == 0.25
    assert parts.grounding == 0.50
    assert parts.total == 1.0


def test_invalid_json_scores_zero() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    parts = score_report("{", manifest)
    assert parts.total == 0.0
    assert parts.schema == parts.coverage == parts.grounding == 0.0


def test_wrong_line_keeps_schema_and_coverage_only() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    parts = score_report(_report(manifest, line=9).model_dump_json(), manifest)
    assert parts.schema == 0.25
    assert parts.coverage == 0.25
    assert parts.grounding == 0.0
    assert parts.total == 0.50


def test_degraded_and_empty_passes_score_zero() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    degraded = _report(manifest, extra_gaps=["llm.schema_invalid:p1"])
    empty = FindingReport(confidence=0, summary=Summary(), issues=[])
    assert score_report(degraded, manifest).total == 0.0
    assert score_report(empty, manifest).total == 0.0


def test_no_ids_awards_coverage_and_grounding_only_without_high_issues() -> None:
    manifest: dict[str, object] = {"ids": [], "na": {}, "expected": []}
    quiet = FindingReport(
        confidence=90,
        summary=Summary(low=1),
        issues=[
            Issue(
                severity=Severity.LOW,
                priority="P3",
                category="arch.dead_code",
                file="app.py",
                line=1,
                title="Unused name",
                explanation="Nothing reads it.",
                recommendedFix="Delete it.",
            )
        ],
    )
    loud = quiet.model_copy(deep=True)
    loud.issues[0].severity = Severity.HIGH
    loud.issues[0].impact = "A high finding is present."
    loud.issues[0].codeExample = "TOKEN = os.environ['TOKEN']"
    assert score_report(quiet, manifest).total == 1.0
    assert score_report(loud, manifest).grounding == 0.0
    assert score_report(loud, manifest).total == 0.5


def test_package_source_does_not_import_dspy() -> None:
    root = Path("src/repolens")
    for path in root.rglob("*.py"):
        text = path.read_text()
        assert "import dspy" not in text
        assert "from dspy" not in text
