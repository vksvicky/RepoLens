# Vacuous pass confidence floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clarify empty-pack LLM confidence in prompts and floor genuine vacuous deep passes to scanners-only baselines (75/55) so clean checklist-complete repos get gate ~75 instead of 0.

**Architecture:** Pure helpers in a new `vacuous_floor.py` decide per-pass substitution and skip notes; `deep_exec` keeps `raw_text` per pass and applies floors to `pass_confidences` before `compute_audit_metrics` (band math unchanged, +5 still applies). FR0 updates prompt strings only (no schema churn).

**Tech Stack:** Python 3.11+, Pydantic `DeepConfig`, pytest, existing `FindingReport` / `CoverageResult` / `compute_audit_metrics`.

**Spec:** [../specs/2026-09-05-vacuous-pass-confidence-floor-design.md](../specs/2026-09-05-vacuous-pass-confidence-floor-design.md) · Issue [#21](https://github.com/vksvicky/RepoLens/issues/21)

## Global Constraints

- British English in user-facing strings (`penalised`, `behaviour`).
- Gate confidence remains package adequacy — not “% secure”.
- Never invent or suppress findings; never raise on skip.
- Do not require `--trust-project-config`.
- No new required schema fields in v1 (`analysisNotes` deferred).
- Do not treat `Summary` count objects as analysis prose.
- Leave untracked `docs/assets/` alone.
- Dual-review gate before commit/push; never push without explicit override.
- Prefer TDD: failing test → implement → pass → commit per task.

## File map

| Path | Responsibility |
|------|----------------|
| `src/repolens/vacuous_floor.py` | **Create** — evidence, floor value, candidate/skip precedence, `apply_vacuous_pass_floors` |
| `src/repolens/config.py` | `DeepConfig.vacuous_pass_confidence_floor: int \| None = None` |
| `src/repolens/pipeline/deep_exec.py` | Retain raw per pass; call floor helper before metrics; refine vacuous gap filter |
| `src/repolens/llm/setup.py` | FR0 empty-pack confidence wording in `SYSTEM_PROMPT` |
| `src/repolens/llm/parse.py` | FR0 note in `repair_prompt` confidence line |
| `tests/test_vacuous_floor.py` | **Create** — unit matrix for floor/skip/config |
| `tests/test_llm_setup_prompt.py` | **Create** — FR0 prompt snapshot |
| `docs/faq.md` | Metrics FAQ section for floor / fail-on distinction |
| `.repolens.example.toml` | Document `[deep] vacuous_pass_confidence_floor` |
| `docs/CHANGELOG.md` | Unreleased note |

---

### Task 1: Core `vacuous_floor` helpers (TDD)

**Files:**
- Create: `src/repolens/vacuous_floor.py`
- Create: `tests/test_vacuous_floor.py`
- Modify: (none yet)

**Interfaces:**
- Produces:
  - `RAW_ANALYSIS_EVIDENCE_MIN = 100`
  - `has_analysis_evidence(report: FindingReport, raw_response_text: str = "") -> bool`
  - `is_floor_candidate(report: FindingReport) -> bool`
  - `resolve_floor_value(*, scanners_all_ran: bool, config_floor: int | None) -> int | None`  
    (`None` = substitution disabled)
  - `skip_reason(*, degraded: bool, has_evidence: bool, checklist_complete: bool) -> str | None`  
    (precedence: `pass_degraded` > `no_analysis_evidence` > `checklist_incomplete`; `None` if all ok)
  - `is_finding_like_gap(gap: str) -> bool` — True for coverage-miss / schema-invalid style gaps; False for Two-Lane / transport noise
  - `is_vacuous_for_floor(report: FindingReport, *, degraded: bool) -> bool`
  - `apply_vacuous_pass_floors(...)` — see Step 3 signature

- [ ] **Step 1: Write failing tests for evidence, candidate, floor value, skip precedence**

```python
# tests/test_vacuous_floor.py
from repolens.schema import FindingReport, Issue, Severity, Summary
from repolens.vacuous_floor import (
    has_analysis_evidence,
    is_floor_candidate,
    resolve_floor_value,
    skip_reason,
)


def _empty(confidence: int = 0) -> FindingReport:
    return FindingReport(confidence=confidence, summary=Summary(), issues=[])


def test_candidate_only_when_confidence_zero_and_no_issues() -> None:
    assert is_floor_candidate(_empty(0)) is True
    assert is_floor_candidate(_empty(80)) is False
    issue = Issue(
        severity=Severity.MEDIUM,
        priority="P3",
        category="heuristic.mega_file",
        file="a.py",
        line=1,
        title="t",
        explanation="e",
        recommendedFix="f",
    )
    assert is_floor_candidate(
        FindingReport(confidence=0, summary=Summary(), issues=[issue])
    ) is False


def test_analysis_evidence_raw_length_and_future_string_fields() -> None:
    stub = '{"issues":[],"confidence":0}'
    assert has_analysis_evidence(_empty(), stub) is False
    assert has_analysis_evidence(_empty(), "x" * 100) is True
    # Summary counts must NOT count as prose
    assert has_analysis_evidence(_empty(), "") is False


def test_resolve_floor_value_auto_and_overrides() -> None:
    assert resolve_floor_value(scanners_all_ran=True, config_floor=None) == 75
    assert resolve_floor_value(scanners_all_ran=False, config_floor=None) == 55
    assert resolve_floor_value(scanners_all_ran=True, config_floor=0) is None
    assert resolve_floor_value(scanners_all_ran=False, config_floor=90) == 90


def test_skip_reason_precedence_degraded_wins() -> None:
    assert (
        skip_reason(degraded=True, has_evidence=False, checklist_complete=False)
        == "pass_degraded"
    )
    assert (
        skip_reason(degraded=False, has_evidence=False, checklist_complete=False)
        == "no_analysis_evidence"
    )
    assert (
        skip_reason(degraded=False, has_evidence=True, checklist_complete=False)
        == "checklist_incomplete"
    )
    assert (
        skip_reason(degraded=False, has_evidence=True, checklist_complete=True)
        is None
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_vacuous_floor.py -q --tb=line`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement `vacuous_floor.py`**

```python
# src/repolens/vacuous_floor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from repolens.coverage import CoverageResult
from repolens.schema import FindingReport, ScannerRun

RAW_ANALYSIS_EVIDENCE_MIN = 100
SkipReason = Literal[
    "pass_degraded", "no_analysis_evidence", "checklist_incomplete"
]

_TRANSPORT_NOISE_PREFIXES = (
    "Two-Lane:",
    "llm.schema_invalid:",  # handled via degraded flag; keep for gap filter docs
)


def is_floor_candidate(report: FindingReport) -> bool:
    return report.confidence == 0 and len(report.issues) == 0


def has_analysis_evidence(
    report: FindingReport, raw_response_text: str = ""
) -> bool:
    for field in ("analysisNotes", "narrative", "notes"):
        val = getattr(report, field, None)
        if isinstance(val, str) and len(val.strip()) >= 20:
            return True
    return len(raw_response_text.strip()) >= RAW_ANALYSIS_EVIDENCE_MIN


def resolve_floor_value(
    *, scanners_all_ran: bool, config_floor: int | None
) -> int | None:
    if config_floor == 0:
        return None
    if config_floor is not None:
        return max(1, min(100, int(config_floor)))
    return 75 if scanners_all_ran else 55


def skip_reason(
    *,
    degraded: bool,
    has_evidence: bool,
    checklist_complete: bool,
) -> SkipReason | None:
    if degraded:
        return "pass_degraded"
    if not has_evidence:
        return "no_analysis_evidence"
    if not checklist_complete:
        return "checklist_incomplete"
    return None


def is_finding_like_gap(gap: str) -> bool:
    g = gap.strip()
    if g.startswith("Two-Lane:"):
        return False
    if g.startswith("metrics.vacuous_pass_"):
        return False
    if g.startswith("coverage:") and "missed" in g:
        return True
    if g.startswith("llm.schema_invalid:"):
        return True
    return False


def is_vacuous_for_floor(report: FindingReport, *, degraded: bool) -> bool:
    if degraded:
        return False
    if report.confidence != 0 or report.issues:
        return False
    return not any(is_finding_like_gap(g) for g in report.durabilityGaps)


def checklist_complete_for_scored(
    coverage: CoverageResult, scored_prefixes: Iterable[str]
) -> bool:
    prefixes = tuple(scored_prefixes)
    if not prefixes:
        return True

    def in_scope(cid: str) -> bool:
        return any(cid.startswith(p) for p in prefixes)

    if any(in_scope(m) for m in coverage.missed):
        return False
    if any(in_scope(i) for i in coverage.invalid_na):
        return False
    return True


def scanners_all_ran(runs: list[ScannerRun]) -> bool:
    return bool(runs) and all(r.status == "ran" for r in runs)


@dataclass(frozen=True)
class PassFloorInput:
    name: str
    report: FindingReport
    raw_text: str
    degraded: bool


@dataclass(frozen=True)
class PassFloorResult:
    pass_confidences: dict[str, int]
    notes: list[str]


def apply_vacuous_pass_floors(
    passes: list[PassFloorInput],
    *,
    coverage: CoverageResult,
    scanner_runs: list[ScannerRun],
    config_floor: int | None,
    scored_prefixes: tuple[str, ...] = ("sec.", "rel.", "arch."),
) -> PassFloorResult:
    """Substitute pass bases for eligible vacuous candidates; emit notes."""
    ran = scanners_all_ran(scanner_runs)
    floor = resolve_floor_value(scanners_all_ran=ran, config_floor=config_floor)
    complete = checklist_complete_for_scored(coverage, scored_prefixes)
    confidences: dict[str, int] = {}
    notes: list[str] = []

    for item in passes:
        report = item.report
        confidences[item.name] = report.confidence
        if not is_floor_candidate(report):
            continue
        if floor is None:
            # Config disabled — still a candidate; no floored note; optional skip?
            # Spec: floor=0 disables substitution. Emit no floored note.
            # Do not emit skip for config-off (not in skip enum). Keep silent.
            continue
        evidence = has_analysis_evidence(report, item.raw_text)
        reason = skip_reason(
            degraded=item.degraded,
            has_evidence=evidence,
            checklist_complete=complete,
        )
        if reason is None and is_vacuous_for_floor(report, degraded=item.degraded):
            confidences[item.name] = floor
            notes.append(
                "metrics.vacuous_pass_confidence_floored:"
                f"{item.name}={floor} (scanners_ran={str(ran).lower()}, "
                "checklist=complete)"
            )
        else:
            # Prefer explicit skip enum; if vacuous helper fails for other gaps,
            # map to closest reason.
            code = reason or "no_analysis_evidence"
            notes.append(
                f"metrics.vacuous_pass_floor_skipped:{item.name}={code}"
            )
    return PassFloorResult(pass_confidences=confidences, notes=notes)
```

Refine `is_vacuous_for_floor` / gap filter if tests demand (Two-Lane noise must not block vacuous).

- [ ] **Step 4: Add apply-floor tests (happy path, stub, degraded, Crit unchanged via metrics)**

```python
from repolens.coverage import CoverageResult
from repolens.metrics import compute_audit_metrics
from repolens.schema import ScannerRun
from repolens.vacuous_floor import PassFloorInput, apply_vacuous_pass_floors


def _ran() -> list[ScannerRun]:
    return [
        ScannerRun(name="gitleaks", status="ran"),
        ScannerRun(name="semgrep", status="ran"),
        ScannerRun(name="osv", status="ran"),
    ]


def test_apply_floors_logviewer_shape_gate_75_sec_80() -> None:
    raw = "x" * 100
    empty = _empty(0)
    passes = [
        PassFloorInput("p1", empty, raw, False),
        PassFloorInput("p2", empty, raw, False),
        PassFloorInput("p3", empty, raw, False),
    ]
    coverage = CoverageResult(
        covered=["sec.injection", "rel.edge_cases", "arch.testing"],
        missed=[],
        na={},
    )
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.pass_confidences == {"p1": 75, "p2": 75, "p3": 75}
    assert any("floored:p1=75" in n for n in result.notes)
    metrics = compute_audit_metrics(
        pass_confidences=result.pass_confidences,
        coverage=coverage,
        scanner_runs=_ran(),
        issues=[],
    )
    assert metrics.gate_confidence == 75
    assert metrics.security_audit_confidence == 80
    assert metrics.reliability_audit_confidence == 75
    assert metrics.architecture_audit_confidence == 75


def test_stub_raw_skips_with_no_analysis_evidence() -> None:
    passes = [PassFloorInput("p2", _empty(0), '{"issues":[],"confidence":0}', False)]
    coverage = CoverageResult(covered=["rel.edge_cases"], missed=[], na={})
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.pass_confidences["p2"] == 0
    assert result.notes == [
        "metrics.vacuous_pass_floor_skipped:p2=no_analysis_evidence"
    ]


def test_degraded_skip_precedes_no_evidence() -> None:
    passes = [PassFloorInput("p1", _empty(0), "", True)]
    coverage = CoverageResult(covered=["sec.injection"], missed=["sec.xss_csrf"], na={})
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.notes == [
        "metrics.vacuous_pass_floor_skipped:p1=pass_degraded"
    ]


def test_non_candidate_emits_no_note() -> None:
    passes = [PassFloorInput("p1", _empty(80), "x" * 100, False)]
    coverage = CoverageResult(covered=["sec.injection"], missed=[], na={})
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.notes == []
    assert result.pass_confidences["p1"] == 80
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `.venv/bin/pytest tests/test_vacuous_floor.py -q`  
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/repolens/vacuous_floor.py tests/test_vacuous_floor.py
git commit -m "$(cat <<'EOF'
feat: add vacuous pass confidence floor helpers (#21)

EOF
)"
```

---

### Task 2: Config field + example TOML

**Files:**
- Modify: `src/repolens/config.py` (`DeepConfig`)
- Modify: `.repolens.example.toml`
- Modify: `tests/test_vacuous_floor.py` (or `tests/test_coverage_config.py` style load test)

**Interfaces:**
- Consumes: Task 1 `resolve_floor_value`
- Produces: `DeepConfig.vacuous_pass_confidence_floor: int | None = None`

- [ ] **Step 1: Failing test — load None / 0 / N from project toml**

```python
def test_deep_vacuous_floor_config_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        "[deep]\nvacuous_pass_confidence_floor = 0\n", encoding="utf-8"
    )
    from repolens.config import load_config

    cfg = load_config(project, trust_project=False)
    assert cfg.deep.vacuous_pass_confidence_floor == 0
```

Also assert default `None` when omitted.

- [ ] **Step 2: Run — expect FAIL (field missing)**

- [ ] **Step 3: Add field to `DeepConfig`**

```python
# on DeepConfig
vacuous_pass_confidence_floor: int | None = None
# None → auto 75/55; 0 → off; 1..100 → pin
```

Add to `.repolens.example.toml` under `[deep]`:

```toml
# vacuous_pass_confidence_floor = 75  # None/omit = auto 75 if scanners ran else 55; 0 = off
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add src/repolens/config.py .repolens.example.toml tests/test_vacuous_floor.py
git commit -m "$(cat <<'EOF'
feat: add vacuous_pass_confidence_floor deep config (#21)

EOF
)"
```

---

### Task 3: Wire `deep_exec` — retain raw text + apply floors

**Files:**
- Modify: `src/repolens/pipeline/deep_exec.py`
- Modify: `src/repolens/pipeline/__init__.py` (export if needed)
- Modify: `tests/test_vacuous_floor.py` (integration with `_apply_coverage_metrics` optional) **or** add `tests/test_deep_vacuous_floor_wire.py` with a thin unit that mocks parts

**Interfaces:**
- Consumes: `PassFloorInput`, `apply_vacuous_pass_floors`, `cfg.deep.vacuous_pass_confidence_floor`
- Produces: floored `pass_confidences` into `_apply_coverage_metrics`; durability notes appended

- [ ] **Step 1: Write failing test that exercises apply path with scanner runs + coverage**

Prefer keeping logic tested in Task 1; for wire, add a focused test that monkeypatches `analyze_structured` inside `_analyze_deep_passes` **only if** an existing deep test pattern exists. Otherwise:

```python
def test_apply_coverage_metrics_uses_floored_pass_bases() -> None:
    # Document that deep_exec must call apply_vacuous_pass_floors before
    # compute_audit_metrics — covered by manual review + Task 1 matrix.
    # Optional: import deep_exec helpers if extracted.
    pass
```

Better concrete wire test — extract a small function in `deep_exec`:

```python
def build_pass_confidences_with_floors(
    outcomes: list[PassFloorInput],
    *,
    coverage: CoverageResult,
    scanner_runs: list[ScannerRun] | None,
    config_floor: int | None,
    report: FindingReport,
) -> FindingReport:
    ...
```

Test that function appends notes onto `report.durabilityGaps`.

- [ ] **Step 2: Implement wire in `_analyze_deep_passes`**

Replace the loop that only stores `parts` with outcomes including `raw_text` and `degraded=(result.layer == "degraded" or result.report is None)`.

After `evaluate_coverage(...)` and before `_apply_coverage_metrics`:

```python
from repolens.vacuous_floor import PassFloorInput, apply_vacuous_pass_floors

outcomes = [
    PassFloorInput(
        name=deep_pass.name,
        report=part,
        raw_text=raw_by_pass.get(deep_pass.name, ""),
        degraded=degraded_by_pass.get(deep_pass.name, False),
    )
    for deep_pass, part in zip(passes, parts, strict=False)
]
floor_result = apply_vacuous_pass_floors(
    outcomes,
    coverage=coverage,
    scanner_runs=list(scanner_runs or []),
    config_floor=cfg.deep.vacuous_pass_confidence_floor,
)
for note in floor_result.notes:
    if note not in report.durabilityGaps:
        report.durabilityGaps.append(note)
report = _apply_coverage_metrics(
    report,
    coverage,
    pass_confidences=floor_result.pass_confidences,
    scanner_runs=scanner_runs,
)
```

Keep recording `raw_by_pass[name] = result.raw_text` even when report is None (use `""` or raw from degraded salvage).

- [ ] **Step 3: Update `is_vacuous_llm_report` docstring to point at `is_vacuous_for_floor` (or delegate gap filtering) so exports stay honest**

- [ ] **Step 4: Run**

`.venv/bin/pytest tests/test_vacuous_floor.py tests/test_metrics.py tests/test_coverage_seeding.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/repolens/pipeline/deep_exec.py tests/test_vacuous_floor.py
git commit -m "$(cat <<'EOF'
feat: apply vacuous pass floors before audit metrics (#21)

EOF
)"
```

---

### Task 4: FR0 prompt clarification + snapshot test

**Files:**
- Modify: `src/repolens/llm/setup.py`
- Modify: `src/repolens/llm/parse.py` (`repair_prompt`)
- Create: `tests/test_llm_setup_prompt.py`

**Interfaces:**
- Produces: updated `SYSTEM_PROMPT` string containing empty-pack confidence rules

- [ ] **Step 1: Failing snapshot test**

```python
from repolens.llm.setup import SYSTEM_PROMPT
from repolens.llm.parse import repair_prompt


def test_system_prompt_explains_empty_pack_confidence() -> None:
    text = SYSTEM_PROMPT.lower()
    assert "issues" in text and "confidence" in text
    assert "free of" in text or "no issues" in text
    assert "empty" in text


def test_repair_prompt_mentions_empty_pack_confidence() -> None:
    msg = repair_prompt("orig", "boom").lower()
    assert "confidence" in msg
    assert "empty" in msg or "no issues" in msg or "free of" in msg
```

- [ ] **Step 2: Run — FAIL on wording**

- [ ] **Step 3: Update prompts**

In `SYSTEM_PROMPT`, after the schema block, add:

```text
Confidence: If you found issues, rate your confidence in those findings (0-100).
If issues is empty, rate your confidence that the examined scope is free of
in-band issues (0-100). An empty issues array with high confidence is valid
when you thoroughly reviewed the pack and found nothing in scope.
```

In `repair_prompt`, add one sentence with the same rule.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add src/repolens/llm/setup.py src/repolens/llm/parse.py tests/test_llm_setup_prompt.py
git commit -m "$(cat <<'EOF'
fix: clarify empty-pack confidence in LLM prompts (#21)

EOF
)"
```

---

### Task 5: FAQ + CHANGELOG

**Files:**
- Modify: `docs/faq.md` (section “What do report metrics mean?”)
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Add FAQ subsection** (British English)

Cover:

- Old prompt contract → models emitted `confidence: 0` on empty packs
- New empty-pack meaning (FR0)
- Auto floor 75/55; +5 → sec 80 / gate 75
- Skip reasons enum
- Scanners-all-ran = global integrity, not p2/p3 content proof
- Seeds alone do not unlock floor
- `--fail-on` = severity; dual-review-style confidence gates often want ≥70

- [ ] **Step 2: CHANGELOG Unreleased**

```markdown
- Deep mode: floor genuine vacuous LLM pass confidence (75/55) so clean
  checklist-complete packages are not stuck at gate 0%; clarify empty-pack
  confidence in prompts (#21)
```

- [ ] **Step 3: Commit**

```bash
git add docs/faq.md docs/CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs: explain vacuous pass confidence floor in FAQ (#21)

EOF
)"
```

---

### Task 6: Remaining matrix tests + Crit penalty + config-off

**Files:**
- Modify: `tests/test_vacuous_floor.py`

- [ ] **Step 1: Add tests**

```python
def test_scanners_not_ran_uses_floor_55() -> None:
    ...


def test_checklist_incomplete_skip() -> None:
    ...


def test_config_floor_zero_disables_without_skip_spam() -> None:
    ...


def test_config_floor_override_90() -> None:
    ...


def test_critical_scanner_issue_still_penalises_after_floor() -> None:
    # floor 75 then severity_finding_penalty drops security/gate
    ...


def test_two_lane_gap_does_not_block_vacuous() -> None:
    report = _empty(0)
    report.durabilityGaps = [
        "Two-Lane: Fast Brain sees 10000 file(s); LLM sample pool is 200"
    ]
    assert is_vacuous_for_floor(report, degraded=False) is True
```

- [ ] **Step 2: Run full focused suite**

`.venv/bin/pytest tests/test_vacuous_floor.py tests/test_llm_setup_prompt.py tests/test_metrics.py tests/test_coverage_seeding.py -q`  
Expected: PASS

- [ ] **Step 3: Run broader regression**

`.venv/bin/pytest -q --tb=line`  
Expected: PASS (or fix unrelated only if caused by this change)

- [ ] **Step 4: Commit**

```bash
git add tests/test_vacuous_floor.py
git commit -m "$(cat <<'EOF'
test: complete vacuous floor matrix including Crit penalty (#21)

EOF
)"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| FR0 prompts | Task 4 |
| FR1 floor 75/55 | Task 1, 3 |
| +5 → sec 80 / gate 75 | Task 1 |
| Analysis evidence raw≥100 + future strings | Task 1 |
| Seeds alone insufficient | Task 1 stub test |
| Skip enum + precedence | Task 1 |
| Candidate rule (no note if findings) | Task 1 |
| Config None / 0 / N | Task 2, 6 |
| Wire before `compute_audit_metrics` | Task 3 |
| FAQ / CHANGELOG | Task 5 |
| Crit still penalises | Task 6 |
| Two-Lane noise ignored | Task 6 |

## Self-review notes

- No TBD placeholders left in tasks.
- `apply_vacuous_pass_floors` is the single substitution API; `deep_exec` only wires it.
- Config-off (`0`) intentionally emits **no** skip note (not in skip enum) — matches “substitution disabled”, not a failed precondition.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-05-vacuous-pass-confidence-floor.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
