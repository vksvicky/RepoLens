# Cross-source SCA deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse cross-source SCA advisories (scanner + LLM) by `(ecosystem, package, advisoryId)` before calculating `severity_finding_penalty` and report summaries, ensuring unique advisories map to unique Critical/High penalties and preventing artificial gate collapse.

**Architecture:** A dedicated helper `dedupe_cross_source_sca_issues` in `sca.py` clusters merged scanner and LLM issues, preserves scanner baseline severities, records all contributing tools in `Issue.evidenceSources`, and records raw finding counts on `FindingReport` before `compute_audit_metrics` and `recount_summary` execute.

**Tech Stack:** Python 3.11+, Pydantic `Issue` / `FindingReport`, pytest.

**Spec:** [../specs/2026-09-06-cross-source-sca-dedupe-design.md](../specs/2026-09-06-cross-source-sca-dedupe-design.md) · Issue [#14](https://github.com/vksvicky/RepoLens/issues/14)

---

## Global Constraints

- British English in user-facing strings (`penalised`, `behaviour`).
- Never overload `cluster_near_duplicates`: theme clustering in `cluster.py` keys on `(file, theme, cwe/title)` and prefers higher severity. SCA dedupe keys on `(ecosystem, package, advisoryId)` and prefers scanner baseline severity.
- If an LLM finding does not cite an explicit advisory ID, leave it untouched (no speculative merge).
- `evidenceSources` is an optional list field on `Issue`, backward-compatible with existing JSON/SARIF consumers.
- Dual-review gate before commit/push; never push without explicit override.
- Prefer TDD: failing test → implement → pass → commit per task.

---

## File Map

| Path | Responsibility |
|------|----------------|
| `src/repolens/scanners/sca.py` | Advisory regex extraction (`CVE-*`, `GHSA-*`, `RUSTSEC-*`, `PYSEC-*`, `GO-*`), package hint extraction, `dedupe_cross_source_sca_issues` |
| `src/repolens/schema.py` | Add `evidenceSources: list[str]` to `Issue`; add `rawCriticalHighCount: int \| None` and `rawTotalFindings: int \| None` to `FindingReport` |
| `src/repolens/pipeline/deep_exec.py` | Call `dedupe_cross_source_sca_issues` after merging parts and before `_apply_coverage_metrics` |
| `src/repolens/pipeline/run.py` | Run cross-source dedupe on final merged issue list (`report.issues + extra_issues`) before recalculating summary and metrics |
| `tests/test_sca_sbom.py` | Unit tests for cross-source advisory deduplication, severity demotion, and regex matching |
| `tests/test_metrics.py` | Test that `severity_finding_penalty` is driven by unique deduplicated issues |

---

### Task 1: Advisory extraction & schema additions (TDD)

**Files:**
- Modify: `src/repolens/schema.py`
- Modify: `src/repolens/scanners/sca.py`
- Modify: `tests/test_sca_sbom.py`

- [x] **Step 1: Write failing tests for advisory extraction**
  Add unit tests in `tests/test_sca_sbom.py`:
  - Recognise `CVE-2024-12345`, `GHSA-3x3c-cg28-v232`, `RUSTSEC-2020-0071`, `PYSEC-2021-100`, `GO-2022-0965` across title and explanation.
  - Return `None` for generic findings without recognized advisory patterns.

- [x] **Step 2: Update regex & schema**
  - In `src/repolens/schema.py`:
    - Add `evidenceSources: list[str] = Field(default_factory=list)` to `Issue`.
    - Add `rawCriticalHighCount: int | None = None` and `rawTotalFindings: int | None = None` to `FindingReport`.
  - In `src/repolens/scanners/sca.py`:
    - Broaden `_CVE_RE` to `_ADVISORY_RE` covering `CVE`, `GHSA`, `RUSTSEC`, `PYSEC`, `GO`.
    - Implement `extract_advisory_id(text: str) -> str | None`.

- [x] **Step 3: Run pytest & verify tests pass**
  Run `pytest tests/test_sca_sbom.py` to confirm extraction passes.

---

### Task 2: Core `dedupe_cross_source_sca_issues` engine (TDD)

**Files:**
- Modify: `src/repolens/scanners/sca.py`
- Modify: `tests/test_sca_sbom.py`

- [x] **Step 1: Write failing tests for cross-source deduplication**
  Add unit tests in `tests/test_sca_sbom.py`:
  - Merge a scanner finding (`HIGH`, category `osv`) and an LLM finding (`CRITICAL`, category `sec.supply_chain`) citing the same CVE and package:
    - Primary finding is the scanner finding.
    - Severity remains `HIGH` (scanner baseline wins; LLM does not inflate to `CRITICAL`).
    - `evidenceSources` contains `["osv", "llm"]`.
  - Merge when only LLM finding exists:
    - Kept as LLM finding with its self-reported severity.
    - `evidenceSources` contains `["llm"]`.
  - Findings without advisory IDs are passed through without modification.
  - Returns `(deduped_issues, raw_critical_high, raw_total)`.

- [x] **Step 2: Implement `dedupe_cross_source_sca_issues`**
  In `src/repolens/scanners/sca.py`:
  ```python
  def dedupe_cross_source_sca_issues(
      issues: list[Issue],
  ) -> tuple[list[Issue], int, int]:
      ...
  ```
  Cluster by `(ecosystem, package, advisory_id)`. Maintain order. If scanner and LLM both match, prefer scanner row and scanner severity, appending all contributing source tags to `evidenceSources`.

- [x] **Step 3: Run pytest**
  Run `pytest tests/test_sca_sbom.py` to confirm deduplication engine passes.

---

### Task 3: Pipeline integration & gate math alignment (TDD)

**Files:**
- Modify: `src/repolens/pipeline/deep_exec.py`
- Modify: `src/repolens/pipeline/run.py`
- Modify: `tests/test_vacuous_floor.py` or `tests/test_metrics.py`

- [x] **Step 1: Write integration test for advisory collapse before gate penalty**
  Test that a review with 2 scanner High advisories and 2 matching LLM Critical advisories yields 2 unique High findings and a finding penalty of `−20` (not `−60`), preserving high confidence.

- [x] **Step 2: Integrate in pipeline**
  - In `src/repolens/pipeline/run.py`:
    - After merging scanner issues and LLM issues (`report.issues = list(report.issues) + extra_issues`), invoke `dedupe_cross_source_sca_issues`.
    - Set `report.rawCriticalHighCount` and `report.rawTotalFindings`.
    - Recount summary (`report.summary = report.recount_summary()`).
    - Recalculate audit metrics so `compute_audit_metrics` evaluates deduplicated issues.
  - In `src/repolens/pipeline/deep_exec.py`:
    - Ensure pass merge respects cross-source deduplication when scanner findings are present.

- [x] **Step 3: Run full test suite**
  Run `pytest tests/test_sca_sbom.py tests/test_metrics.py tests/test_vacuous_floor.py`.

---

## Verification Plan

### Automated Tests
- `pytest tests/test_sca_sbom.py`
- `pytest tests/test_metrics.py`
- `pytest tests/test_vacuous_floor.py`
- `ruff check src/ tests/`

### Manual Verification
- Verify that LogViewer mock data collapses duplicate advisories from 4–6 down to 2, and reports `Unique Critical/High: 2 (4 raw)`.
