# Metis agent harness → RepoLens adopt / refuse

**Status:** Steps 1–6 + A–E thin MVPs + #86–#89 CLI (2026-10-06). Plan-level `role_packs` still fills the same ~100k char budget per pass. Two 32B Audits on this tree both ran with **`role_packs=false`**. **No Metis % claim.**
**Sources:** [Wholiver/metis](https://github.com/Wholiver/metis) · [metisagent.tech/compare](https://metisagent.tech/compare/)  
**Related:** [competitive-landscape-sonar-alternatives-2026.md](./competitive-landscape-sonar-alternatives-2026.md) · [sonargraph-architect-comparison.md](./sonargraph-architect-comparison.md) · [which-command.md](../which-command.md) · [zugel-comparison-and-roadmap.md](./zugel-comparison-and-roadmap.md)

Metis is a **coding-agent harness** (plan → edit → test → self-heal). RepoLens is a **zero-infra dual-review / audit CLI**. Borrow **mechanisms**; do not become an autonomous editor.

---

## Category boundary (refuse product shape)

| Metis | RepoLens |
| --- | --- |
| Edits the tree and heals until tests pass | Audits the tree and fails a gate |
| Investigator / Builder / Reviewer implementers | Investigator / Auditor / Verifier **roles inside Slow Brain** |
| Desktop agent workspace | Thin editor client over CLI (Sonargraph note) — not a Metis desktop |

**Refuse:** autonomous edit loops, recursive implementer agents, worktree builders, video evidence, “boost coding 50%” framing.

---

## Guardrails (locked)

### Protect `--dry-run`

Today `--dry-run` is an **inventory dump without scanners** (`_write_dry_run`). Overloading it with scanners or forecast tables would break existing CI scripts.

**Plan** (deterministic recon before LLM) is either:

- `--scanners-only` **plus** a forecaster, or  
- a dedicated `repolens plan`

Do **not** change `--dry-run` semantics.

### Honesty on “~60% token cut”

That figure is a **Metis marketing claim**. RepoLens claims a cut only after dogfood instrumentation of **chars-in / chars-out per pass** (and wall clock on the same machine). Production-honesty positioning forbids inventing percentages.

### Extend `ProvenanceBlock` (borrowing E)

RepoLens already emits SARIF/JSON with `ProvenanceBlock` (version, git SHA, …). Add dirty-tree, scanner binary digests, prompt/template hashes, and journal tip hash **on that block**. Do **not** invent a disconnected parallel envelope format.

### Steps 1 and 2 run in parallel

Step 2 (`.repolens/journal.jsonl`) has **zero** model-cost or prompt dependency. Ship it alongside Step 1 (`[deep].role_packs`) so interrupted 6–7h runs become visible immediately while role packing cuts tokens.

---

## Part 1 — Validated proposals (vs code today)

### 1. Role-aware context slicing + inter-pass summaries — **adopt; highest ROI**

**Code today**

- `plan_deep_passes()` in `deep.py` builds **one** `packed = budget_files(...)` and reuses it for every band (P1/P2/P3).
- `budget_files` is greedy on `FileEntry.size` (byte estimate), not role or symbol value.
- `file_outline.py` exists and is used heavily by `explain.py`, **not** by deep pack assembly.

**Adopt**

| Role / pass | Pack content |
| --- | --- |
| P1 Security | Entry points, auth/crypto/exec/SQL/config/secrets hotspots; demote CSS, pure transformers, large generated trees |
| P2 Reliability | Error paths, txn boundaries, concurrency, cleanup; demote pure UI chrome |
| P3 Architecture | Prefer `format_file_outline` + grimp import graph; **full bodies only for hot cycle modules** |

**Inter-pass rolling summary:** after pass \(N-1\), emit ≤~200 tokens of confirmed finding titles + covered checklist ids into pass \(N\) prompt. Do not re-ship the entire prior raw pack.

### 2. Verification gate language — **adopt; sharpen beyond location tags**

**Code today**

- `verify_findings.py` only re-checks **Critical** locations via `verify_issue_location`.
- Failures annotate `[verify: location unconfirmed]`; they **do not** change gate %.

**Adopt**

1. AST/symbol grounding (cited symbol exists near the reported line) for Crit/High (and optionally Medium architecture claims).
2. Bifurcate report sections: **Grounded** vs **Suspect / Unverified**.
3. Gate penalty: unverified Crit/High lowers security (or owning) band — not silent prose.

Keep verify non-fatal for report write; make it **fatal for confidence honesty**.

### 3. Append-only review journal — **adopt; complements pass cache**

**Code today**

- Pass cache (`.repolens/passes/*.json`) resumes matching P1/P2/P3/coverage when files + model + RepoLens version + template match.
- Operators still cannot see *why* a 7h run stopped or what finished.

**Adopt:** `.repolens/journal.jsonl` events (`pass_started` / `pass_completed` / `queue_wait` / `interrupted` / `verify_*`) with role, model, file counts, char budget, duration, finding counts, coverage gaps.

**`--resume`:** prefer “read journal + pass cache” over inventing a second cache. Journal is the human-readable post-mortem; pass cache stays the skip oracle.

### 4. Plan ↔ Audit naming — **adopt in docs/CLI first**

| Operator word | RepoLens meaning | Command today |
| --- | --- | --- |
| **Plan** (recon) | Scanners + inventory + cyclicity snapshot + **pack preview** | Closest: `--scanners-only`; true Plan = scanners-only + forecaster or `repolens plan` — **not** `--dry-run` |
| **Audit** (synthesis) | Slow Brain role passes + verify | `--deep` / recommended command 1 |

Document in `which-command.md` and progress lines as `Plan (Fast Brain)` / `Audit (Slow Brain)` before adding aliases.

---

## Part 2 — Five more borrowings (fit check)

| ID | Idea | Fit | Note |
| --- | --- | --- | --- |
| **A** | Pre-flight forecaster (`repolens plan` or scanners-only + forecast) | **Adopt** | Do **not** change `--dry-run`. New table: packs per role, char/token estimate, outline-vs-full lists, provider ETA |
| **B** | Blast-radius pack for `--git-diff` | **Adopt** | Today: change-set paths only. Extend: changed ∪ direct imports ∪ direct importers (grimp); rest outline-only or excluded |
| **C** | Negative-evidence / N/A truth check | **Adopt** | Vacuous-pass floor exists; add inventory keyword/path check that **rejects** N/A when the claimed absence is false → `hallucination_residual` |
| **D** | `repolens diff-audit A B` | **Adopt (later)** | Fingerprints already stable; emit resolved / new / debt drift (cyclicity + complexity). M&A / release story |
| **E** | Attestation fields | **Extend `ProvenanceBlock`** | Dirty-tree, scanner binary digests, prompt/template hash, journal tip hash — same JSON/SARIF provenance path |

---

## Part 3 — Execution roadmap

| Step | Focus | Deliverable | Depends |
| --- | --- | --- | --- |
| **1** | Compaction & role slicing | `[deep].role_packs`; per-band packs; P3 outline-heavy; inter-pass ≤200-token summary; **chars-in/out metrics** | — |
| **2** | Journal + resume UX | `.repolens/journal.jsonl`; interrupt post-mortem; `--resume` via journal + pass cache | **Parallel with Step 1** |
| **3** | Pre-flight forecaster | `repolens plan` (or scanners-only + forecast flag) | Better after Step 1 planner; thin v1 can forecast current same-pack behavior |
| **4** | Hardened verification gate | Symbol grounding; Grounded/Suspect; gate % penalty for unverified Crit/High | See multi-language watch-out below |
| **5** | Nomenclature + compare page | Plan/Audit labels; `docs/compare.md` (“we audit, they edit”) | Docs anytime |
| **6** | Learned adaptations | `.repolens/` skip/hotspot prefs from feedback patterns | After journal optional |

**Not in this roadmap:** Metis desktop, edit/self-heal loops, video tools.

---

## Technical watch-outs (Step 1 / Step 4)

### 1. Pass-cache key must include prior-pass summary hash

**Today:** pass cache keys hash packed files + model + RepoLens version + template + band. Passes are independent.

**With rolling summaries:** pass \(N\)’s prompt depends on pass \(N-1\)’s summary. If role packs are on, the cache key for pass \(N\) **must** incorporate a hash of that summary (or of pass \(N-1\)’s cached report digest). Otherwise a resume/replay can condition P2/P3 on an empty or stale P1 summary.

### 2. P3 must not budget with raw `entry.size`

`budget_files()` (`deep.py`) uses on-disk byte size so planning does not read contents. Outlines from `format_file_outline` are typically ~85–95% smaller than raw files.

If P3 still budgets with `entry.size`, the pass cap fills after ~15 large files even though ~150 outlines would fit. **P3 needs an outline-cost estimator** (e.g. line_count × ~30 chars, or a separate outline-budget pass) — not raw `entry.size`.

### 3. Symbol grounding must not punish non-Python (Step 4)

Python can use `ast.parse()`. JS/TS/Go/Rust/C# rely on regex extractors in `file_outline.py`. Verification matchers must treat regex-extracted symbols as first-class evidence so multi-language repos do not collect false **unverified** gate penalties.

---

## Already aligned (do not rebuild)

- Model freedom / Ollama / BYOK  
- Machine-wide local fair queue + pass-by-pass tickets  
- Pass cache resume (versioned keys) — **extend** for summary hash when role packs on  
- P1→P2→P3 bands + coverage closure  
- `--verify-findings` (location, Critical-only — extend, don’t replace)  
- Feedback demotion / ignore fingerprints  

---

## Success metrics (dogfood)

| Metric | Baseline (selfdog full deep `…_2054`) | After this slice |
| --- | --- | --- |
| Wall clock (32B local, full tree) | **1h 0m 24s** (`qwen2.5-coder:32b`, `role_packs=false`, Fast/Slow 435 files) | **1h 11m 50s** (`…_0642`, same model, `role_packs=false`, 437 files). Not a like-for-like `role_packs` experiment — tree grew |
| Plan estimated chars (RepoLens tree, `--full-audit`, 2026-10-06) | `--no-role-packs`: 299,997 chars (P1/P2/P3 each 44 full files @ ~100k) | `--role-packs`: 299,998 chars (P1 32 full / P2 25 full / **P3 149 outlines** @ ~100k). Same fill of `chars_per_pass`; more P3 files, not fewer tokens |
| Journal `chars_in`/`chars_out` (`role_packs=false`) | `…_2054` P1+P2+P3: **345,911 in / 15,821 out** | `…_0642` P1+P2+P3: **362,036 in / 16,200 out**. Still **no** `role_packs=true` 32B Audit — do not claim a cut vs Metis ~60% |
| Gate honesty | Unverified Crit not scored | Unverified Crit/High lowers band (`--verify-findings`) |
| Operator interrupt | Opaque | Journal names last finished pass; `--resume` / `--no-resume` |

---

## Next implementation slice (approved direction)

Run **in parallel**:

**Step 1** — `[deep].role_packs = true` (default off until dogfood):

1. Distinct file lists (or outline mode) per band.  
2. P3 uses outline-cost estimator; fixture proves P3 char budget ≪ P1 on large-body trees.  
3. Inter-pass summary in pass \(N\) prompt; **pass-cache key includes summary hash**.  
4. Emit chars-in / chars-out per pass for honesty metrics.

**Step 2** — `.repolens/journal.jsonl` + interrupt / resume UX (no LLM dependency).

Then Step 3 forecaster without touching `--dry-run` semantics.
