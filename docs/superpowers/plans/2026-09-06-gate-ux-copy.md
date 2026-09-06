# Gate UX & copy alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align CLI and Markdown report copy with `docs/faq.md` (British English), explicitly clarify that gate confidence represents review-package adequacy rather than a "% secure" score, and display unique vs raw Critical/High finding counts.

**Architecture:** Update `render_report_markdown` in `src/repolens/report.py` and CLI summary formatters in `src/repolens/` to render the explanatory alert and display `Unique Critical/High: N (M raw)` using fields populated by Issue #14.

**Tech Stack:** Python 3.11+, Rich console formatting, existing Markdown builders in `report.py`, pytest.

**Spec:** [../specs/2026-09-06-gate-ux-copy-design.md](../specs/2026-09-06-gate-ux-copy-design.md) · Issue [#17](https://github.com/vksvicky/RepoLens/issues/17)

---

## Global Constraints

- British English in all user-facing strings (`penalised`, `adequacy`, `behaviour`).
- Text must strictly match `docs/faq.md`: gate confidence = review-package adequacy (coverage + open severity penalties), not a "% secure" score.
- Do not alter numerical formulas in `compute_audit_metrics`.
- Local UI calibrations are explicitly deferred to #17b (post-Phase 7 start).
- Prefer TDD: failing test → implement → pass → commit per task.

---

## File Map

| Path | Responsibility |
|------|----------------|
| `src/repolens/report.py` | Add `[!NOTE]` alert to Markdown report header; add unique vs raw row to Markdown summary table |
| `src/repolens/cli/` (or `progress.py` / `pipeline/run.py`) | Format terminal summary table with FAQ-aligned one-liner and unique vs raw counts |
| `tests/test_report.py` | Unit tests for Markdown report rendering of copy note and unique/raw finding lines |
| `tests/test_cli.py` | Snapshot/output tests for CLI terminal formatting |
| `docs/phases.md` | Document #17 MVP completion and pin #17b tracking |

---

### Task 1: Markdown Report Presentation (TDD)

**Files:**
- Modify: `src/repolens/report.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: Write failing tests for report Markdown copy**
  In `tests/test_report.py`:
  - Assert that generated Markdown includes the GitHub-style `> [!NOTE]` callout regarding review-package adequacy.
  - Assert that when `report.rawCriticalHighCount = 4` and unique Critical/High is 2, the summary table renders `2 unique (4 raw across tools)`.
  - Assert that when `rawCriticalHighCount` is None or equals unique, only the single count renders.

- [ ] **Step 2: Update `render_report_markdown`**
  In `src/repolens/report.py`:
  - Insert explanatory note beneath the metadata table.
  - Format the summary table rows to display unique and raw numbers when deduplication occurred.

- [ ] **Step 3: Run pytest**
  Run `pytest tests/test_report.py` to confirm tests pass.

---

### Task 2: CLI Console Output & One-liner (TDD)

**Files:**
- Modify: `src/repolens/pipeline/run.py` or CLI summary renderer
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for CLI console summary**
  Verify terminal output includes:
  - `* Gate confidence reflects review-package adequacy (checklist coverage + open severity penalties), not a "% secure" score.`
  - `Unique Critical/High: N (M raw across tools)` when raw count > unique count.

- [ ] **Step 2: Update CLI summary formatting**
  Implement the formatting using Rich console styling in the appropriate CLI output handler.

- [ ] **Step 3: Run pytest**
  Run `pytest tests/test_cli.py` to verify console output formatting.

---

### Task 3: Pin #17b Tracking

- [ ] **Step 1: Document #17b follow-up**
  Ensure GitHub issue #17 (or child issue) is pinned with:
  - Track: `#17b` — Local UI / desktop calibrations (`attack_surface=local_ui`, repetitive Medium clustering).
  - Milestone: Post-Phase 7 start.

---

## Verification Plan

### Automated Tests
- `pytest tests/test_report.py`
- `pytest tests/test_cli.py`
- `ruff check src/ tests/`

### Manual Verification
- Run `repolens review --path .` on a sample repository with mocked multi-source findings; verify that CLI terminal output displays the one-liner cleanly without wrapping errors.
