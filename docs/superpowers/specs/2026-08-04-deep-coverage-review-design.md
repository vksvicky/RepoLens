# Deep coverage review (B+C+D, then A as quality multiplier)

**Status:** Design approved (Approach 1; phasing **1** = B+C+D first, A later; **graceful 4-layer structured LLM spine** locked)  
**Date:** 2026-08-04  
**Depends on:** Rules registry (see §3.2; replaces hard-coded playbook filenames), adaptive packs, scanners, FindingReport schema + JSON coercion  
**Source authorities (content provenance for default rules, not runtime paths):**  
- `/Users/vivek/Development/Security Analysis Instruction for Cursor AI.md` (P1)  
- `/Users/vivek/Development/Architecture Review.md` (P2/P3 + full-audit scores)  
Default shipped rule bodies may be derived from these; **runtime must never require those absolute paths or fixed `security.md` / `architecture.md` names.**

## 1. Problem

Single-shot LLM reviews on large repos (e.g. PatternSorcerer ~184 files / ~780k chars) produce thin or schema-broken reports that miss vibes-style structural findings (mega-files, UI duplication, `.gitignore` / secrets-process hygiene) even when a strong local model (qwen2.5-coder:32b) is used. Users may pick **any** Ollama/cloud model; freestyle JSON must **not** abort the product after a long wait. Cloud Claude (Haiku/Opus) is a quality multiplier, not a substitute for a pipeline that **covers the dual-review checklists** and **always delivers a report**.

## 2. Goals

1. **Beat vibes-style depth** on checklist coverage: every point in the Security Instruction and Architecture Review MDs is either evidenced by an issue or an explicit `coverage:<id>: N/A — reason`.  
2. Make **local models** viable via chunked passes + heuristics (B+C+D).  
3. Keep **cloud providers** as a drop-in quality multiplier (A) after B+C+D ships.  
4. Preserve scanners (gitleaks/semgrep/osv) as complementary P1 automation.  
5. **Model-agnostic reliability:** BYO model never leaves the user with only a fatal validation error; always write a usable report.

## 3. Decisions (locked)

| Decision | Choice |
|----------|--------|
| Phasing | **B+C+D first**; **A** (Anthropic/OpenAI) later as provider-only multiplier |
| Architecture | Coverage-driven chunked pipeline + heuristic pre-pass |
| LLM structured output | **Graceful 4-layer spine** (ask → coerce → micro-repair → degrade); see §3.1 |
| On total LLM parse failure | Write **degraded report** (scanners + heuristics + any partial issues) + exit **0**; save raw under `.repolens/` |
| Default deep mode | **On** for `review` / `architecture` / `sentinel` LLM runs; `--no-deep` restores single-shot |
| Full audit | `--full-audit` uses deep **and** full Architecture checklist + scores |
| Rules | **Registry by rule id** (enable/disable/override); no hard-coded MD filenames in deep/coverage code |
| Coverage | Coverage IDs reference `rule_id` + section keys, not filesystem paths |
| Heuristics | Stdlib-only; emit FindingReport issues + hot-file boosts; not a Semgrep replacement |
| Merge | Dedupe issues; confidence = min (or documented blend) across LLM passes |

### 3.1 Graceful structured LLM spine (reliability)

Every LLM call (deep pass or single-shot) goes through:

1. **Ask for structure** — Prefer provider JSON/schema mode when available (Ollama `format`, OpenAI `json_schema` / response_format, Anthropic tool/structured where applicable). Never trust alone.  
2. **Coerce** — Normalize freestyle fields (severity case, aliases, defaults) before Pydantic.  
3. **Micro-repair** — If still invalid: **second call with only** the broken payload + schema (not the full repo prompt).  
4. **Degrade, don’t die** — If still invalid: merge scanners + heuristics + any salvageable issues; add durabilityGaps (`llm.schema_invalid` / per-pass note); save raw text to `.repolens/last_llm_raw_<pass>.txt` (or similar); **write the markdown/JSON report**; process exit **0**. Optional later: free-text → structure extract call.

Weak models → thinner / more heuristic reports. Strong models → full FindingReport. The CLI remains useful either way.

### 3.2 Rules registry (not hard-coded MD paths)

Review guidance is a set of **rules**, each with:

| Field | Meaning |
|-------|---------|
| `id` | Stable id, e.g. `security`, `architecture`, `reliability` |
| `band` | `p1` / `p2` / `p3` |
| `enabled` | bool (user/project can disable) |
| `title` | Display label |
| `body` | Markdown/text content loaded at runtime |
| `coverage_ids` | Optional list of coverage checklist ids this rule owns |

**Resolution order (later CLI/UI will mutate the upper layers):**

1. Project: `.repolens/rules/<id>.md` + `.repolens/rules.json` (enable/disable overrides)  
2. User: `~/.config/repolens/rules/` + user rules manifest  
3. Packaged defaults: e.g. `repolens/rules/` (or current playbooks package data **as default rule bodies**, keyed by id — filenames are an implementation detail of the default pack only)

**Deep/coverage/pipeline code** must call `load_enabled_rules(band=...)` / `get_rule(id)` — **never** `load_playbook("security.md")` or absolute paths to the author’s Development folder.

**Future (out of scope for first slice, API must not block it):**  
`repolens rules list|enable|disable|add|edit` and a UI to manage the same registry.

**Migration:** Existing `playbooks_for_mode` becomes a thin adapter over the registry so current CLI keeps working while deep mode uses rules explicitly.

## 4. Pipeline (B)

When LLM runs and deep is enabled:

1. Inventory + adaptive pack (existing) + scanners (existing).  
2. **Heuristics (D)** → issues + hot paths.  
3. **Pass P1 — Security:** files = hot ∪ adaptive ∪ security globs; prompt = **enabled P1 rules’ bodies** + coverage IDs for those rules.  
4. **Pass P2 — Reliability:** enabled P2 rules + coverage ids.  
5. **Pass P3 — Architecture:** enabled P3 rules (scoped vs full-audit selects which coverage ids / optional full architecture rule variant).  
6. Merge reports + heuristic issues; write markdown/JSON; emit coverage summary.

`sentinel` runs P1 rules (+ heuristics security-relevant). `architecture` runs P3 rules. `review` runs P1→P2→P3.

Progress UI: `→ Deep: heuristics…`, `→ Deep pass k/n …`, final coverage tally.

## 5. Coverage matrix (C)

**Artifact:** packaged with default rules, e.g. `repolens/rules/coverage.json` (path is pack-internal; loaded via rules/coverage API, not hard-coded by callers).

Each coverage entry includes: `id`, `rule_id`, `band`, `full_audit_only` (bool), `title`, optional `playbook_anchor` (section heading inside the **rule body**, not a filesystem path).

Example id families (defaults seeded from the Security / Architecture authorities):  
`sec.*` → `rule_id=security`; `arch.*` → `rule_id=architecture`; reliability ids → `rule_id=reliability`.

**CI sync test:** every coverage id references an **enabled-by-default rule id** that exists in the default pack; anchors resolve inside that rule’s body (or marked `implicit`). Tests must **not** open `/Users/vivek/Development/...` paths.

**Prompt contract per pass:** For each assigned coverage ID (from enabled rules only), the model must either:

- emit one or more FindingReport issues addressing it, or  
- add `durabilityGaps` entry: `coverage:<id>: N/A — <reason>`.

Disabled rules → their coverage ids are omitted (or auto N/A: `rule disabled`).

**Report:** Optional `coverage` block in JSON; markdown section listing covered / N/A / missed. Missed IDs (neither issue nor N/A) lower confidence and appear under durability gaps.

## 6. Heuristics (D)

**Module:** `src/repolens/heuristics/`

| Signal | Default severity | Notes |
|--------|------------------|-------|
| File LOC ≥ threshold (default 500) | MEDIUM | Mega-file / LocalizedString-class |
| Sibling name pairs (`Extract*`/`Replace*`, etc.) | MEDIUM | Duplication candidates; optional light line-overlap later |
| `.gitignore` missing `.env` / key secret patterns when env/notarize scripts exist | MEDIUM | Secrets-process gap |
| Shell/docs password / Apple ID / notarize env without keychain guidance | LOW–MEDIUM | Process hygiene |
| TODO/FIXME / commented-out density | LOW | Code quality |
| Missing Dependabot/CodeQL/etc. when package manifests exist | LOW | CI scanner gap note |

Heuristics run before LLM passes; issues merge into final report; paths feed pack selection.

**Non-goals:** AST clone detection; replacing Semgrep/OSV/gitleaks.

## 7. Phase A (later — quality multiplier)

No separate pipeline. User selects Anthropic/OpenAI via `repolens init` / guided model provider. Same deep passes + coverage + heuristics. Document: cloud models improve adherence and depth; deep mode is required for checklist completeness on large repos.

## 8. CLI & guided UX

- `--deep` / `--no-deep`  
- Config: `[deep] enabled`, `chars_per_pass`, `mega_file_lines`  
- Guided: deep toggle with recommendation “on for full audits / large repos”  
- Timeout suggestions remain model-size aware (existing guided helpers)

## 9. Testing & acceptance

- Unit tests: heuristics fixtures; merge/dedupe; coverage N/A parsing; matrix ID sync vs **default rule bodies** (via registry).  
- Integration: mocked multi-pass LLM → merged report (no live Ollama in CI).  
- **Acceptance (manual):** PatternSorcerer `review --full-audit --deep` with local 32B (or smaller packs) surfaces themes: LocalizedString mega-file, Extract/Replace duplication candidate, `.gitignore`/env secrets hygiene — without requiring Claude.  
- Claude run optional for A validation after ship.

## 10. Non-goals (this program)

- Hosted SaaS UI  
- Replacing mature scanners  
- Guaranteeing bit-for-bit match with CleanVibes/SecureVibes copy (checklist completeness + finding depth are the success metrics)

## 11. Rollout

1. **Graceful structured spine** (ask → coerce → micro-repair → degrade + exit 0) — applies to all LLM paths  
2. Rules registry + coverage matrix + CI sync / default-rule drift check  
3. Heuristics module + tests  
4. Deep multi-pass pipeline + merge + progress + flags (each pass uses §3.1)  
5. Guided + docs + CHANGELOG  
6. Phase A docs / guided cloud tip only (no new architecture)
