# Deep Coverage Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship B+C+D deep coverage review (heuristics + chunked P1→P3 passes + checklist coverage matrix) so large-repo local reviews beat thin single-shot reports; leave cloud (A) as a later provider multiplier. **BYO models never abort the run on schema failure** — always write a report (exit 0).

**Architecture:** Graceful 4-layer LLM spine (ask → coerce → micro-repair → degrade). Heuristics emit FindingReport issues and hot paths; deep mode runs capped multi-pass LLM calls with **enabled rule bodies** (registry) + coverage IDs; merge/dedupe into one report with coverage tally. `--no-deep` preserves single-shot. Cloud later uses the same pipeline.

**Tech Stack:** Python 3.11+, existing `pipeline`/`schema`/`progress`/`llm`, new `rules` registry (playbooks adapter), stdlib heuristics, pytest, Typer CLI.

## Global Constraints

- Phasing: **B+C+D first**; **A** later as provider-only multiplier
- LLM spine: ask for structure → coerce → micro-repair (schema-only) → degrade; **exit 0** with report on total LLM parse failure
- Deep default **on** for LLM runs; `--no-deep` restores single-shot
- `--full-audit` → deep + full Architecture checklist + scores
- Rules via **registry by id** (project → user → packaged defaults); no hard-coded `security.md` / `architecture.md` or author machine paths in deep/coverage code
- Coverage IDs reference `rule_id` + anchors inside rule bodies
- Heuristics stdlib-only; not a Semgrep replacement
- No live Ollama in CI; PatternSorcerer themes are manual acceptance
- Commits only when user asks; never push without explicit override

**Spec:** [docs/superpowers/specs/2026-08-04-deep-coverage-review-design.md](../specs/2026-08-04-deep-coverage-review-design.md)

## File structure

| Path | Responsibility |
|------|----------------|
| `src/repolens/llm_structured.py` (or extend `llm.py`) | 4-layer spine: provider JSON mode, coerce, micro-repair, degrade + raw save |
| `src/repolens/rules/` | Rules registry: load/enable/disable, default pack, future CLI hooks |
| `src/repolens/rules/defaults/` (or reuse package data) | Default rule bodies + `coverage.json` + manifest (`id`, `band`, `enabled`) |
| `src/repolens/coverage.py` | Load matrix via rules API, parse N/A gaps, score coverage |
| `src/repolens/heuristics/` | Pre-pass signals → issues + hot paths |
| `src/repolens/deep.py` | Pass planning from **enabled rules**, pack budgeting, merge/dedupe |
| `src/repolens/playbooks.py` | Thin adapter over rules registry (compat) |
| `src/repolens/pipeline.py` | Wire spine + deep into `run_review` |
| `src/repolens/config.py` | `[deep]` settings |
| `src/repolens/cli.py` | `--deep` / `--no-deep` (rules CLI later) |
| `src/repolens/report.py` | Coverage section in markdown/JSON |
| `scripts/repolens_guided.py` | Deep toggle |
| Tests | `test_llm_structured`, `test_rules`, `test_coverage*`, `test_heuristics`, `test_deep*` |
| Docs | FAQ, setup, CHANGELOG, phases |

---

### Task 0: Graceful structured LLM spine (reliability)

**Files:**
- Create/Modify: `src/repolens/llm.py` and/or `src/repolens/llm_structured.py`
- Modify: `src/repolens/pipeline.py` — replace fatal `_analyze_with_repair` abort with spine; never skip writing report
- Create: `tests/test_llm_structured.py`

**Interfaces:**
- `analyze_structured(prompt, model_cfg, *, pass_id: str, progress=None) -> StructuredLlmResult`
- `StructuredLlmResult(report: FindingReport | None, raw_text: str, layer: Literal["ok","coerced","micro_repair","degraded"], error: str | None)`
- On degraded: `report` may be empty issues; caller merges scanners/heuristics; raw saved under `.repolens/last_llm_raw_<pass_id>.txt`

- [x] **Step 1:** Failing tests: (a) invalid freestyle JSON → coerce success; (b) uncoerceable JSON → micro-repair mock returns valid; (c) both fail → `layer=degraded`, no exception, raw persisted path returned.

- [x] **Step 2:** Implement layers; prefer Ollama/OpenAI JSON format flags when provider supports; micro-repair prompt is schema-only (no repo files).

- [x] **Step 3:** Pipeline/CLI: on degraded, still `write_markdown_report` / JSON; CLI exit **0**; print warning that LLM output was degraded.

- [ ] **Step 4:** Commit when user asks.

---

### Task 1: Rules registry + coverage matrix

**Files:**
- Create: `src/repolens/rules/` (`registry.py`, `defaults/manifest.json`, default rule body files keyed by id, `defaults/coverage.json`)
- Create: `src/repolens/coverage.py`
- Create: `tests/test_rules_registry.py`, `tests/test_coverage_matrix.py`
- Modify: `src/repolens/playbooks.py` — adapt to `get_rule("security")` etc. (no hard-coded path constants in deep code)

**Interfaces:**
- `list_rules(*, include_disabled=False) -> list[Rule]`
- `get_rule(rule_id: str) -> Rule`
- `load_enabled_rules(*, band: str | None = None) -> list[Rule]`
- `load_coverage_matrix() -> CoverageMatrix`  # from default pack / overrides
- `coverage_ids_for_pass(pass_id, *, full_audit, enabled_rule_ids) -> list[str]`
- `parse_coverage_notes(gaps) -> dict[str, str]`
- `evaluate_coverage(ids, issues, gaps) -> CoverageResult`

- [ ] **Step 1:** Failing tests: registry resolves default `security` / `architecture` / `reliability` by **id**; project override `.repolens/rules/<id>.md` wins; disabled rule omitted from `load_enabled_rules`. Coverage sync test uses rule bodies from registry — **not** absolute paths or literal `security.md` strings in deep modules.

- [ ] **Step 2:** Seed default pack from current playbook content (copy once into defaults); author `coverage.json` with `rule_id` on every entry.

- [ ] **Step 3:** Implement registry + coverage; keep `playbooks_for_mode` working via adapter.

- [ ] **Step 4:** Commit when user asks.

---

### Task 2: Heuristics module (D)

**Files:**
- Create: `src/repolens/heuristics/__init__.py`, `mega_files.py`, `siblings.py`, `gitignore_secrets.py`, `scripts_hygiene.py`, `ci_gaps.py`, `runner.py`
- Create: `tests/test_heuristics.py`
- Create: `tests/fixtures/heuristics/` (tiny synthetic trees)

**Interfaces:**
- `run_heuristics(root: Path, entries: list[FileEntry], *, mega_file_lines: int = 500) -> HeuristicResult`
- `HeuristicResult(issues: list[Issue], hot_paths: list[str])`

- [ ] **Step 1:** TDD mega-file ≥500 LOC → MEDIUM issue; missing `.env` in gitignore when `scripts/*notarize*` mentions password → MEDIUM; `ExtractToolView`/`ReplaceToolView` sibling pair → MEDIUM candidate.

- [ ] **Step 2:** Implement signals from spec §6; keep severities as specified.

- [ ] **Step 3:** Commit when user asks.

---

### Task 3: Deep pass planner + merge (B core)

**Files:**
- Create: `src/repolens/deep.py`
- Create: `tests/test_deep.py`

**Interfaces:**
- `plan_deep_passes(mode, *, full_audit, entries, hot_paths, adaptive_paths, chars_per_pass, rules: list[Rule]) -> list[DeepPass]`
- `DeepPass(name, rule_ids, coverage_ids, files: list[FileEntry])`
- `budget_files(entries, *, max_chars) -> list[FileEntry]`
- `merge_reports(parts: list[FindingReport], heuristic_issues: list[Issue]) -> FindingReport`
- `build_deep_prompt(pass: DeepPass, rules: list[Rule], coverage_ids) -> str`  # concatenates enabled rule bodies by id

- [ ] **Step 1:** Tests for budgeting (never exceed char budget), pass ordering P1→P2→P3, dedupe `(file, title)`, confidence = min of parts.

- [ ] **Step 2:** Implement planner/merge/prompt builder including coverage contract sentence from spec §5.

- [ ] **Step 3:** Commit when user asks.

---

### Task 4: Wire pipeline + config + CLI

**Files:**
- Modify: `src/repolens/config.py` — `DeepConfig(enabled=True, chars_per_pass=100_000, mega_file_lines=500)`
- Modify: `.repolens.example.toml`
- Modify: `src/repolens/pipeline.py` — deep branch inside LLM path
- Modify: `src/repolens/cli.py` — `--deep/--no-deep` (typer dual option or `--deep/--no-deep` with default None → config)
- Modify: `src/repolens/report.py` — coverage markdown section
- Create: `tests/test_pipeline_deep.py` (mock `analyze` per pass)

- [ ] **Step 1:** Failing integration test: with deep on and mocked analyze returning one issue per pass + coverage N/A gaps, final report merges 3+ heuristic issues and lists coverage.

- [ ] **Step 2:** Implement wire-up; `--no-deep` calls existing single `_analyze_with_repair` once.

- [ ] **Step 3:** Progress lines for heuristics and each pass.

- [ ] **Step 4:** Commit when user asks.

---

### Task 5: Guided script + docs + Phase A tip

**Files:**
- Modify: `scripts/repolens_guided.py` — deep Y/n (default Y for full-audit / review)
- Modify: `tests/test_guided_script.py`
- Modify: `docs/faq.md`, `docs/setup-ai-and-scanners.md`, `docs/try-on-your-repo.md`, `docs/phases.md`, `docs/CHANGELOG.md`, `README.md` as needed
- Note Phase A: “Anthropic/OpenAI use the same `--deep` pipeline”

- [x] **Step 1:** Guided emits `--deep` / `--no-deep` when CLI supports it (probe help).

- [x] **Step 2:** Docs describe deep coverage vs single-shot; PatternSorcerer-oriented tip.

- [ ] **Step 3:** Commit when user asks.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Graceful 4-layer spine + exit 0 degrade | 0 |
| Rules registry (no hard-coded MD paths) + coverage | 1 |
| Heuristics D | 2 |
| Chunked P1→P3 + budgets | 3–4 |
| Merge/dedupe/confidence | 3–4 |
| `--deep` / `--no-deep` / config | 4 |
| Report coverage section | 4 |
| Guided + docs | 5 |
| Phase A later (docs only) | 5 |
| CI: no live Ollama | 0–4 |

## Plan self-review

- No TBD placeholders; interfaces named for later tasks.
- Task 0 is the reliability spine — ship before or with Task 4 wire-up.
- A deferred to docs-only in Task 5 per locked phasing.
- Commit steps gated on user request per repo policy.
