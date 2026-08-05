# Self-review hardening (RepoLens dogfood backlog)

**Status:** Approved in chat 2026-08-05 (approach B — full backlog, PR order 1→2→3→4)  
**Source report:** `reports/gate_review_report_review_2026-08-05_2113.md` (~40 findings)  
**Language:** Report/heuristic prose stays British English.

## Goal

Make the next deep self-review honest: remove noise, close Highs, harden the guided script, then split mega-files without behaviour change. Docs polish last.

## Non-goals

- Phase 6 explain / diagrams  
- Provider aliases / native SDKs  
- Changing deep coverage algorithms beyond ignore / heuristic tuning  
- “Fixing” security playbook wording by stuffing keychain keywords into every doc (prefer skip rules)

## PR plan

### PR 1 — Noise & truth

| Change | Detail |
|--------|--------|
| Inventory ignores | Add `.superpowers` (and similar agent scratch) to `IGNORE_DIR_NAMES` so diffs never enter packs |
| Mega-file excludes | Default / example globs: `**/.superpowers/**`, keep docs/pbxproj patterns |
| Fixture silence | Skip `tests/fixtures/**` for sibling + scripts_hygiene heuristics (fixtures are intentional) |
| scripts_hygiene scope | Only flag **executable-ish** scripts (`.sh`/`.ps1`/notarize names), **not** `.md` playbooks/docs that discuss passwords pedagogically — or require password *and* shell script context |
| SECURITY.md | Prefer GitHub Private Vulnerability Reporting; remove placeholder “email when published” or add a real contact if one exists |
| Security playbook | Explicit bullet: mature scanners (Dependabot/Renovate, CodeQL/Semgrep, secret scanning) complement LLM review |
| British English | Keep existing `prose.py` instruction |

**Exit:** Re-run heuristics-only or scanners+heuristics path → no findings on `.superpowers/*`, fixtures, or playbook “password” false positives.

### PR 2 — Guided script reliability

File: `scripts/repolens_guided.py` (+ tests in `tests/test_guided_script.py`).

| Finding theme | Fix |
|---------------|-----|
| subprocess Highs | Broaden catch to `Exception` with log + empty fallback **or** document that OSError/SubprocessError is sufficient and add timeout/`check` hardening; prefer small, tested helper `_run_capture` |
| URL validation | Validate remote URL / github path shapes before building argv |
| “Hardcoded secrets in CLI args” | Ensure prompts never echo secrets; use env var names only in examples |
| Edge empty input | Harden `_prompt_text` empty/default loop |
| Readability nits | Small cleanups in `_collect_choices` without a full rewrite (full split → PR 3) |

**Exit:** Guided unit tests green; Highs for guided script closed or severity re-justified with tests.

### PR 3 — Mega-file splits (behaviour-preserving)

Target threshold: `mega_file_lines` default 500 (or document intentional exceptions).

| Current | Proposed modules (illustrative) |
|---------|----------------------------------|
| `src/repolens/cli.py` | `cli/app.py` (Typer root) + `cli/commands_review.py` / `plugins.py` / `adaptive.py` / `export.py` — thin `__init__` re-exports `app` for entry point |
| `src/repolens/llm.py` | `llm/client.py` (dispatch) + `llm/openai_stream.py` + `llm/anthropic_stream.py` + `llm/errors.py` |
| `src/repolens/pipeline.py` | `pipeline/run.py` + `pipeline/prompt.py` + `pipeline/deep_exec.py` (or keep `deep.py` and thin `pipeline.py`) |
| `scripts/repolens_guided.py` | `scripts/guided/` package: `prompts.py`, `argv.py`, `caps.py`, `__main__.py` — keep `repolens-guided.sh` wrapper |

**Rules:** Move-only commits preferred; no behaviour change; full `pytest` green after each file family; public import paths preserved via re-exports where needed (`repolens.cli:app`, `repolens.llm.analyze`, etc.).

**Exit:** Those paths under threshold **or** listed in project `[deep] mega_file_exclude_globs` with a one-line rationale (prefer split).

### PR 4 — Docs polish

- `docs/try-on-your-repo.md` Low readability/redundancy findings  
- FAQ cross-link to this spec under “self-review / dogfood”

## Testing & verification

| Layer | PR 1 | PR 2 | PR 3 | PR 4 |
|-------|------|------|------|------|
| Unit | heuristic / inventory ignore tests | guided script tests | import + existing suites | none / light |
| Dogfood | `repolens review --path . --scanners-only` + short heuristic assert | guided dry paths | full `pytest` | optional |
| Deep self-review | Optional after PR 1 | Optional after PR 2 | Recommended after PR 3 | — |

## Success criteria (end of B)

1. High findings from 2026-08-05_2113 closed or superseded.  
2. Noise buckets (`.superpowers`, fixtures, playbook password spam) near zero.  
3. Core modules split or explicitly excluded with rationale.  
4. Spec + FAQ pointer committed; British English retained.

## Sequencing

**Locked:** PR 1 → 2 → 3 → 4.
