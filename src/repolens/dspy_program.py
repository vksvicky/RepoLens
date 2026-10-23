"""Parse a compiled Slow Brain instruction file and score a report against its manifest.

The review path uses the standard library only. Nothing in this module imports DSPy
or calls a model. A maintainer compiles the two strings offline; a review only reads them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from repolens.coverage import parse_coverage_notes
from repolens.schema import FindingReport, Severity
from repolens.themes import canonicalize_coverage_id, theme_id_for_category

KIND = "repolens.dspy-instruction"
PROGRAM_VERSION = 1
OPTIMIZER = "instruction-only"
PASS_NAMES = frozenset({"p1", "p2", "p3", "coverage"})
MAX_FORMAT_HINT = 1_000
MAX_INSTRUCTION_TAIL = 2_000
FORBIDDEN_KEYS = frozenset({"examples", "fewshot", "demonstrations"})
FIXTURE_MARK = "tests/fixtures/dspy"
SCHEMA_WEIGHT = 0.25
COVERAGE_WEIGHT = 0.25
GROUNDING_WEIGHT = 0.50
_LINE_CITE = re.compile(r"\bline\s*\d+", re.IGNORECASE)
_SOURCE_PATH = re.compile(
    r"(?<![\w.])[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|kt|rb|php)\b",
    re.IGNORECASE,
)


class ProgramRejected(ValueError):
    """The instruction file failed validation and must not enter the prompt."""


@dataclass(frozen=True)
class InstructionProgram:
    """The two strings a review may substitute, plus the cache digest."""

    pass_name: str
    instruction_tail: str
    format_hint: str
    digest: str


@dataclass(frozen=True)
class PassProgram:
    """What one pass should do with the configured instruction file."""

    tail: str | None = None
    hint: str | None = None
    cache_hash: str | None = None
    provenance: str | None = None


@dataclass(frozen=True)
class MetricParts:
    """One total in ``[0, 1]`` and the three parts a test can assert."""

    total: float
    schema: float
    coverage: float
    grounding: float


_ZERO = MetricParts(0.0, 0.0, 0.0, 0.0)


def instruction_digest(pass_name: str, instruction_tail: str, format_hint: str) -> str:
    """SHA-256 of the pass name, the tail, and the hint, joined by NUL."""
    raw = f"{pass_name}\0{instruction_tail}\0{format_hint}".encode()
    return hashlib.sha256(raw).hexdigest()


def parse_program(data: Mapping[str, Any]) -> InstructionProgram:
    """Validate one instruction object. Key order does not change the digest."""
    if not isinstance(data, Mapping):
        raise ProgramRejected("program must be a JSON object")
    _reject_forbidden(data)
    _require_identity(data)
    tail = _require_text(data, "instructionTail", MAX_INSTRUCTION_TAIL)
    hint = _require_text(data, "formatHint", MAX_FORMAT_HINT)
    _reject_citations(tail)
    _reject_citations(hint)
    pass_name = str(data["pass"])
    return InstructionProgram(
        pass_name=pass_name,
        instruction_tail=tail,
        format_hint=hint,
        digest=instruction_digest(pass_name, tail, hint),
    )


def program_for_pass(setting: str, root: Path, pass_name: str) -> PassProgram:
    """Load the instruction for one pass. A missing directory file stays stock."""
    if not setting.strip():
        return PassProgram()
    location = Path(setting)
    if not location.is_absolute():
        location = root / location
    if location.is_dir():
        return _program_from_file(location / f"{pass_name}.json", pass_name)
    if not location.is_file():
        return PassProgram(provenance="rejected")
    return _required_program(location, pass_name)


def instruction_hashes(setting: str, root: Path) -> dict[str, str]:
    """Provenance map for the four pass names. Stock passes are omitted."""
    found: dict[str, str] = {}
    for pass_name in ("p1", "p2", "p3", "coverage"):
        loaded = program_for_pass(setting, root, pass_name)
        if loaded.provenance is not None:
            found[pass_name] = loaded.provenance
    return found


def score_report(
    candidate: str | Mapping[str, Any] | FindingReport,
    manifest: Mapping[str, Any],
) -> MetricParts:
    """Score a candidate report. Invalid, degraded, and empty passes are zero."""
    report = _as_report(candidate)
    if report is None or _is_degraded(report) or _is_empty(report):
        return _ZERO
    schema = SCHEMA_WEIGHT
    coverage = _coverage_part(report, manifest)
    grounding = _grounding_part(report, manifest)
    return MetricParts(schema + coverage + grounding, schema, coverage, grounding)


def _reject_forbidden(data: Mapping[str, Any]) -> None:
    found = FORBIDDEN_KEYS.intersection(data)
    if found:
        raise ProgramRejected(f"forbidden keys: {sorted(found)}")


def _require_identity(data: Mapping[str, Any]) -> None:
    if data.get("kind") != KIND:
        raise ProgramRejected("kind must be repolens.dspy-instruction")
    if data.get("version") != PROGRAM_VERSION:
        raise ProgramRejected("version must be 1")
    if data.get("optimizer") != OPTIMIZER:
        raise ProgramRejected("optimizer must be instruction-only")
    if data.get("pass") not in PASS_NAMES:
        raise ProgramRejected("pass must be p1, p2, p3, or coverage")
    if data.get("demos") != []:
        raise ProgramRejected("demos must be an empty list")


def _require_text(data: Mapping[str, Any], field: str, limit: int) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise ProgramRejected(f"{field} must be a string")
    if len(value) > limit:
        raise ProgramRejected(f"{field} is longer than {limit} characters")
    return value


def _reject_citations(text: str) -> None:
    if FIXTURE_MARK in text.lower():
        raise ProgramRejected("instruction text names the fixture tree")
    if _SOURCE_PATH.search(text):
        raise ProgramRejected("instruction text names a source file")
    if _LINE_CITE.search(text):
        raise ProgramRejected("instruction text cites a line number")


def _as_report(candidate: str | Mapping[str, Any] | FindingReport) -> FindingReport | None:
    if isinstance(candidate, FindingReport):
        return candidate
    try:
        payload = json.loads(candidate) if isinstance(candidate, str) else candidate
        if not isinstance(payload, Mapping):
            return None
        return FindingReport.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError):
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return None


def _is_degraded(report: FindingReport) -> bool:
    return any(
        gap.startswith("llm.schema_invalid:") or "degraded" in gap.lower()
        for gap in report.durabilityGaps
    )


def _is_empty(report: FindingReport) -> bool:
    return not report.issues and not parse_coverage_notes(report.durabilityGaps)


def _coverage_part(report: FindingReport, manifest: Mapping[str, Any]) -> float:
    raw_ids = manifest.get("ids") or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return COVERAGE_WEIGHT
    notes = parse_coverage_notes(report.durabilityGaps)
    satisfied = sum(1 for cid in raw_ids if _id_satisfied(str(cid), report, notes))
    return COVERAGE_WEIGHT * (satisfied / len(raw_ids))


def _id_satisfied(cov_id: str, report: FindingReport, notes: dict[str, str]) -> bool:
    canon = canonicalize_coverage_id(cov_id)
    for issue in report.issues:
        mapped = theme_id_for_category(issue.category)
        if mapped == canon or canonicalize_coverage_id(issue.category) == canon:
            return True
    reason = notes.get(canon) or notes.get(cov_id)
    return bool(reason and reason.strip())


def _grounding_part(report: FindingReport, manifest: Mapping[str, Any]) -> float:
    expected = manifest.get("expected") or []
    if not isinstance(expected, list) or not expected:
        high = any(issue.severity in {Severity.CRITICAL, Severity.HIGH} for issue in report.issues)
        return 0.0 if high else GROUNDING_WEIGHT
    matched = sum(1 for item in expected if isinstance(item, Mapping) and _matches(report, item))
    return GROUNDING_WEIGHT * (matched / len(expected))


def _program_from_file(path: Path, pass_name: str) -> PassProgram:
    if not path.is_file():
        return PassProgram()
    return _parsed_program(path, pass_name)


def _required_program(path: Path, pass_name: str) -> PassProgram:
    if not path.is_file():
        return PassProgram(provenance="rejected")
    return _parsed_program(path, pass_name)


def _parsed_program(path: Path, pass_name: str) -> PassProgram:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        program = parse_program(data)
    except OSError:
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return PassProgram(provenance="rejected")
    except (json.JSONDecodeError, ProgramRejected, TypeError):
        return PassProgram(provenance="rejected")
    if program.pass_name != pass_name:
        return PassProgram()
    return PassProgram(
        tail=program.instruction_tail,
        hint=program.format_hint,
        cache_hash=program.digest,
        provenance=program.digest,
    )


def _matches(report: FindingReport, expected: Mapping[str, Any]) -> bool:
    want_file = str(expected.get("file", "")).replace("\\", "/").removeprefix("./")
    want_line = expected.get("line")
    want_category = expected.get("category")
    for issue in report.issues:
        path = issue.file.replace("\\", "/").removeprefix("./")
        if path == want_file and issue.line == want_line and issue.category == want_category:
            return True
    return False
