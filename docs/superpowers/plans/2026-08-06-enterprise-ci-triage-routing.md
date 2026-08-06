# Enterprise CI triage routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RepoLens deployable on large (10k+ file) enterprise repos by ensuring CI/PR runs **never** full-LLM the tree: scanners gate on the diff; the LLM runs only on triage hits (snippet-scoped) or is bypassed when scanners are clean.

**Architecture:** Extend the existing scanner merge + adaptive/`--changed` pack selection with an explicit **CI triage** mode. Scanners run first on changed paths; findings drive a tiny LLM pack (file + nearby lines / function). Fail-on uses scanner-sourced issues by default. Full `--deep` remains for scheduled/release audits. Aligns with [phase-6.x design §6.3](../../design/phase-6.x-scanner-depth-ci-gates-and-credibility.md).

**Tech Stack:** Python 3.11+, existing `pipeline/run.py`, `pipeline/deep_exec.py`, scanner plugins, Typer CLI, pytest.

**Spec / design:** [phase-6.x-scanner-depth-ci-gates-and-credibility.md](../../design/phase-6.x-scanner-depth-ci-gates-and-credibility.md) (Phase 6.3)  
**Blog context:** [enterprise-scale-llm-review-ci.md](../../blog-ideas/enterprise-scale-llm-review-ci.md)

**Depends on:** Phase 3 scanners, Phase 5 adaptive/`--changed`, Phase 6 issue IDs (for later suppressions).  
**Does not include:** SARIF anchoring (6.4), `.repolens-ignore` (6.7), Trivy/Checkov (6.1) — separate plans; this plan may stub hooks for them.

**Commits only when user asks; never push without override.**

---

## File structure

| Path | Responsibility |
|------|----------------|
| `src/repolens/triage.py` (new) | Pure helpers: decide LLM bypass vs hit pack; build snippet pack from scanner issues |
| `src/repolens/config.py` | `CiConfig` / flags: `triage_routing`, `llm_on_clean_diff`, max snippets |
| `src/repolens/pipeline/run.py` | Wire triage before LLM; record meta (`llmBypassed`, `triageHits`) |
| `src/repolens/cli/commands_review.py` | `--ci` flag (implies triage defaults) |
| `src/repolens/schema.py` | Optional report meta fields for triage outcome |
| `tests/test_triage.py` | Unit tests for routing decisions |
| `docs/ci.md`, `docs/faq.md` | Enterprise PR recipe |
| `.repolens.example.toml` | `[ci]` / triage knobs |

---

### Task 1: Triage decision helpers (TDD)

**Files:** `tests/test_triage.py`, `src/repolens/triage.py`

- [ ] **Step 1:** Write failing tests:
  - No scanner issues on changed paths → `should_invoke_llm is False`
  - Scanner High on `a.py:42` → LLM pack contains only that file (or snippet window), not full tree
  - Suppressed / empty severity below floor → bypass
  - Explicit override `llm_on_clean_diff=True` → LLM may still run (document as non-CI)
- [ ] **Step 2:** Implement `triage_llm_plan(scanner_issues, changed_files, config) -> TriagePlan`
- [ ] **Step 3:** Run `pytest tests/test_triage.py -q` — pass
- [ ] **Step 4:** Commit when user asks

---

### Task 2: Wire triage into `run_review` + `--ci`

**Files:** `src/repolens/pipeline/run.py`, `src/repolens/cli/commands_review.py`, `src/repolens/config.py`, `src/repolens/schema.py`

- [ ] **Step 1:** Add config defaults: triage on when `--ci` or `[ci].triage_routing = true`
- [ ] **Step 2:** After scanners, before LLM/deep: apply `TriagePlan`
  - Bypass → skip LLM; still write report (scanners + heuristics); set meta flags
  - Hits → build minimal pack (snippets); prefer single-shot or one explain-style pass over full p1/p2/p3 deep unless configured
- [ ] **Step 3:** `--fail-on` documentation: CI recipe fails on **scanner** High/Critical; LLM narrative optional
- [ ] **Step 4:** Tests: integration with mocked scanners + mocked LLM (assert LLM not called when clean)
- [ ] **Step 5:** Commit when user asks

---

### Task 3: Pack / budget guards

**Files:** `src/repolens/triage.py`, `config.py`, docs

- [ ] **Step 1:** Caps: `max_triage_files`, `max_snippet_chars`, `max_llm_passes_in_ci` (default 1)
- [ ] **Step 2:** If caps exceeded → truncate with report note; never silently expand to full deep
- [ ] **Step 3:** Progress UX: print “LLM bypassed (scanners clean)” or “LLM triage: N hit(s)”
- [ ] **Step 4:** Tests for caps
- [ ] **Step 5:** Commit when user asks

---

### Task 4: Docs & Action recipe

**Files:** `docs/ci.md`, `docs/faq.md`, `docs/try-on-your-repo.md` (short pointer), `.repolens.example.toml`, `action.yml` if needed

- [ ] **Step 1:** Document enterprise PR recipe: `repolens review --ci --changed --scanners auto --fail-on HIGH`
- [ ] **Step 2:** Explicit: full `--deep` is for scheduled/release audits, not default CI
- [ ] **Step 3:** Link blog idea + Phase 6.x design
- [ ] **Step 4:** Commit when user asks

---

## Spec coverage checklist

| Design item (6.3) | Task |
|-------------------|------|
| Triage routing architecture | 1–2 |
| LLM bypass when scanners clean | 1–2 |
| Snippet-scoped LLM on hits | 1–2 |
| Scanners-as-gate / fail-on | 2, 4 |
| Budget honesty (no fake &lt;5m SLA) | 3–4 |
| Provenance / source tags | Follow-up if not already present; minimal: meta `llmBypassed` |

## Out of scope (next plans)

- SARIF Verification & Anchor → Phase 6.4 plan  
- `.repolens-ignore` → Phase 6.7 plan  
- Trivy/Checkov plugins → Phase 6.1 plan  

## Plan self-review

- CI path never requires full-repo deep on 10k files.  
- Heuristics may still run cheaply; they must not force a full LLM pack in `--ci`.  
- British English in user-facing docs.
