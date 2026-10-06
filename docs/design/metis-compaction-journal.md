# Metis Step 1∥2 completion — content-aware compaction + journal post-mortem

Date: 2026-10-06  
Status: **implemented** (slice C on main); slice D like-for-like dogfood still separate  
Parent rudder: [metis-agent-comparison.md](./metis-agent-comparison.md)

## Problem

Steps 1–2 and thin MVPs already shipped (`role_packs`, outline P3, inter-pass summary + cache hash, `.repolens/journal.jsonl`, `--resume`, `repolens journal` chars totals). What remains before a publishable dogfood (slice D) is surgical completion of the original Step 1∥2 contract:

- **A — Compaction:** path-only hints miss generic names (`client.py`, `db.py`); P3 is outline-only even for modules in import cycles.
- **B — Journal UX:** no `verify_*` events, no pass/queue duration on completed rows, weak human post-mortem.

Dogfooding a 32B Audit before A+B lands would understate compaction and force a second 6–7h run.

## Goal (slice C)

Finish Step 1∥2 so a subsequent like-for-like dogfood (same `max_files`, `role_packs` on vs off) is the definitive honesty benchmark. No Metis ~60% claim. Keep `role_packs` **default off**. Do **not** change `--dry-run`.

## Non-goals

- Split P3 into two bands / passes
- AST or Fast Brain scanner-coupled sniffing
- Default `role_packs=true`
- 32B dogfood in this slice (that is slice D)
- Autocomplete edit/self-heal product shape

## What already ships (do not rebuild)

- `[deep].role_packs` + CLI `--role-packs` / `--no-role-packs`
- Per-band path-hint ordering; P3 `estimate_outline_chars` + `pack_mode=outline`
- `compact_pass_summary` + `pass_key(..., prior_summary=...)`
- Journal `pass_started` / `pass_completed` / `queue_wait` / `interrupted`
- `repolens journal` chars_in/out + last finished
- `repolens plan`, verify Grounded/Suspect, blast-radius, ProvenanceBlock tip hash

---

## Section 1 — Architecture

### Approach (locked)

**Mixed P3 + 4KB regex sniff** inside one `p3` pass. Rejected: split P3 passes; reuse Fast Brain scanners as sniff.

### Three units

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `src/repolens/pack_sniff.py` | P1/P2 content score from path + first 4KB; demote CSS/scss/svg/min/fixtures | `FileEntry` only |
| `plan_deep_passes` (in `deep.py`) | Order + budget; P3 hybrid when cycles present | Optional `GraphResult` |
| `journal` + `commands_journal` | `review_started`, `verify_*`, duration fields; human post-mortem | Existing JSONL |

### DeepPass shape

- Keep `files: list[FileEntry]` ordered.
- Add `file_pack_modes: dict[str, str]` mapping `relative` → `"full"` \| `"outline"` (empty/absent ⇒ all full).
- Pass-level `pack_mode`: `"full"` \| `"outline"` \| `"hybrid"`.
- When hybrid has **zero** cycle hits in the packed set → use `"outline"` (no empty “Active cycle modules” header).

### Asset demotion (P1/P2)

Demoted suffixes/patterns (`.css`, `.scss`, `.svg`, `.min.js`, `.min.css`, large fixture/mocks paths, lockfiles as listed in implementation) are **omitted** from P1/P2 packs, not merely sorted last.

### Graph degradation

If `GraphResult` is SKIPPED/FAILED or absent: P3 stays outline-only; append durability gap `graph.p3_outline_only: <reason>`. Audit continues.

### Guardrails

- `--dry-run` remains inventory-only.
- Sniff bytes never enter the journal.
- No invented token-cut percentages in CLI or docs.

---

## Section 2 — Data flow & tests

### Compaction flow (`role_packs=true`)

```
FileEntry[]
  → pack_sniff.score(band, entry)     # path + first 4KB; demote → omit P1/P2
  → plan_deep_passes(..., graph?)
       P1/P2: order by sniff score; budget full size; pack_mode=full
       P3: cycle-first order; hybrid cost = size for cycle hits, outline cost else
  → pass_key(..., pack_mode, file_pack_modes)
  → _append_source_files(hybrid): two subheads
  → journal pass_* (+ pass_duration_ms, queue_wait_ms)
```

`role_packs=false`: shared full pack unchanged; sniff/hybrid off; journal still records durations when passes run.

### Four locked contracts

1. **Pass cache** — `pass_key` digests `pack_mode` and sorted `f"{relative}:{mode}"` lines so outline vs hybrid never collide.
2. **Hybrid prompt** — two explicit markdown subheads; never interleave full and outline bodies:

   ```markdown
   ## Source files
   ### Active cycle modules (full bodies for refactoring context)
   #### path...
   ### Architectural context (structure outlines)
   #### path...
   ```

3. **Cycle matching** — normalize both sides: strip known suffixes, unify separators; match dotted form (`/`→`.`) and path form so `repolens.graph.build` matches `…/graph/build.py`.
4. **Sniff I/O** — `open("rb").read(4096)` + `decode(errors="ignore")` inside `except (OSError, UnicodeError)`; fail → path-only score, never raise.

### P3 cycle-first ordering (locked polish)

When cycles exist, `_order_for_band(..., band="p3")` places **cycle-member files first**, then hot/adaptive, then the rest, so full-body budget is not exhausted by peripheral outlines.

### Journal / verify flow

```
review_started {run_id, model, role_packs}
pass_started → queue_wait (existing seconds) → pass_completed
  (+ pass_duration_ms; queue_wait_ms on pass row)
verify_started → apply_verify_findings → verify_completed
  {grounded_count, suspect_count, duration_ms}
interrupted {last_finished}   # existing
```

Keep existing `queue_wait.seconds` for back-compat; new fields use integer **milliseconds**.

### TDD order

| Area | Cases |
|------|--------|
| `pack_sniff` | P1 boost on SQL/exec in generic `client.py`; P2 on retry/lock; demoted assets; unreadable → 0 |
| `plan_deep_passes` | P1 omits demoted; P3 hybrid with cycles; outline-only + gap when graph failed; dotted cycle ↔ path |
| `pass_key` | outline vs hybrid different; flipping one file mode flips key |
| `_append_source_files` | hybrid dual headers; cycle full body; non-cycle outline |
| journal / CLI | durations; verify counts; INTERRUPTED post-mortem + Resume line; `--json` machine shape |
| regression | `role_packs=false`; existing role_packs / journal / plan tests |

---

## Section 3 — Error handling & CLI post-mortem

### Degradation matrix

| Failure | Behavior |
|---------|----------|
| Sniff I/O / binary | Path-only score; silent |
| Graph SKIPPED/FAILED | P3 outline-only + durability gap |
| Graph OK, zero cycle hits in pack | `pack_mode=outline` |
| Tight budget | Cycle-first order prefers cycle full bodies |
| Journal OSError | Swallow (existing) |
| Verify off | No `verify_*` events; omit Verify line in CLI |
| Interrupt | `interrupted` + Status INTERRUPTED |
| `role_packs=false` | No sniff/hybrid |

### Human CLI (format ms; store ints)

```text
Run ID: 2026-10-06T15-30-12Z
Status: INTERRUPTED during P2 Reliability
role_packs: on
Completed passes:
  ✓ P1 Security: 18 files (full), 4 findings, 14m 12s (queue wait: 4.2s)
  — P2 Reliability: started, not completed
Verify: (not run)
Last finished: P1 Security
Resume: repolens review --resume --path <root>
Honesty: chars_in=… chars_out=… (not a Metis % claim)
```

`format_duration_ms(ms)` → `"< 1s"` \| `"4.2s"` \| `"14m 12s"`. `--json` keeps raw integers / event counts; no human duration strings required in JSON.

Clean completion: `Status: COMPLETED` + full pass list + Verify when present.

### Success criteria

- Generic `client.py` with SQL/exec enters P1 ahead of demoted assets  
- CSS/min/fixtures absent from P1/P2 packs  
- Cycle modules full in hybrid P3; others outline  
- Cache key changes with pack / per-file modes  
- Journal/CLI separate queue wait vs inference; no Metis %  
- Focused tests + `role_packs=false` regressions green  

### Out of scope (slice D / later)

Like-for-like 32B dogfood; flipping default `role_packs`; AST sniff; split P3 bands; `--dry-run` changes.

---

## Implementation notes (for writing-plans)

1. Wire `GraphResult` into deep planning from the existing Fast Brain graph already computed in the review pipeline (do not re-analyse solely for packing when a result is already on `ReviewState`).
2. Update `repolens plan` forecast rows to show `hybrid` when applicable.
3. Update [metis-agent-comparison.md](./metis-agent-comparison.md) status after ship; keep honesty table free of invented cuts.
4. Coverage ≥ 85% on new/changed modules; TDD red→green per unit.

## Acceptance

Slice C is done when the TDD table above is green on CI and the human `repolens journal` post-mortem matches the copy above for interrupt and completed runs. Slice D (dogfood) is a separate explicit run.
