# Phase 6 Issue Explain + Foolproof Diagrams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assign hybrid issue IDs (`stableId` + `runId`), add `[explain]` toggle + `repolens explain <uuid>` / `review --explain`, and produce deep-dive Markdown with solutions and Mermaid diagrams that never fail the command on bad diagram syntax or missing renderers.

**Architecture:** IDs stamped when building/merging the FindingReport; explain resolves UUID from latest report JSON; dedicated `explain.py` + `diagrams.py` use the existing LLM spine; Mermaid validate → one repair → textual fallback; optional image is best-effort only.

**Tech Stack:** Python 3.11+, uuid, existing `llm_structured` / schema / report / Typer, pytest. Optional external `mmdc`/kroki — never required.

## Global Constraints

- Spec: [docs/superpowers/specs/2026-08-04-phase-6-issue-explain-diagrams-design.md](../specs/2026-08-04-phase-6-issue-explain-diagrams-design.md)
- **Depends on Phase 5.1** (honest metrics) before shipping explain UX
- Explain exit 0 unless UUID missing / explain disabled
- Commits only when user asks; never push without override

## File structure

| Path | Responsibility |
|------|----------------|
| `src/repolens/issue_ids.py` | `stable_id(...)`, `new_run_id()`, stamp issues |
| `src/repolens/schema.py` | `Issue.stableId`, `Issue.runId` optional fields |
| `src/repolens/explain.py` | Load report, resolve UUID, build explain prompt, write artifact |
| `src/repolens/diagrams.py` | Mermaid extract/validate/repair/fallback/optional render |
| `src/repolens/config.py` | `ExplainConfig` |
| `src/repolens/cli.py` | `explain` command; `review --explain` |
| `src/repolens/pipeline.py` | Stamp IDs; write `.repolens/last_report.json`; optional post-review explain |
| `src/repolens/report.py` | Show IDs on each issue in Markdown |
| Tests | `test_issue_ids.py`, `test_diagrams.py`, `test_explain.py`, CLI tests |
| Docs | FAQ, CHANGELOG, phases, example.toml |

---

### Task 1: Issue IDs

- [x] **Step 1:** Failing tests: same (category, file, title) → same `stableId`; each stamp gets unique `runId`.
- [x] **Step 2:** UUID v5 with fixed RepoLens namespace for stableId; uuid4 for runId; stamp in merge/pipeline.
- [x] **Step 3:** Commit when user asks.

### Task 2: Diagram spine (no LLM)

- [x] **Step 1:** Tests: valid mermaid passes; broken mermaid → repair hook mocked → still bad → textual fallback; render failure → keep mermaid + note.
- [x] **Step 2:** Implement `process_diagram(raw: str, *, render_image: str) -> DiagramResult`.
- [x] **Step 3:** Commit when user asks.

### Task 3: Explain command

- [x] **Step 1:** Integration test with mocked `analyze_raw` writes `explain_*.md` containing Problem / Solutions / Diagram.
- [x] **Step 2:** Typer `repolens explain <uuid>` — lookup latest JSON + last_report pointer; respect `[explain].enabled`. Wire CLI flags from spec §5: `--no-diagram` (skip Mermaid/diagram section generation) and `--render-image` (force/opt into optional PNG/SVG when a renderer is available; honor `[explain].render_image` when flag omitted). Pass both through to `explain.py` / `diagrams.process_diagram`.
- [x] **Step 3:** Commit when user asks.

### Task 4: Review `--explain` + config + docs

- [x] **Step 1:** CLI flag + config; after review, explain listed UUIDs.
- [x] **Step 2:** Docs + CHANGELOG + phases checkboxes.
- [x] **Step 3:** Commit when user asks.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| stableId + runId | 1 |
| Foolproof Mermaid spine | 2 |
| `repolens explain` | 3 |
| Toggle + `review --explain` | 4 |
| Exit 0 on diagram failure | 2–3 |

## Plan self-review

- No image renderer required at runtime.
- Phase 5.1 prerequisite called out in Global Constraints.
- Enterprise CI remains Phase 7 (out of scope).
