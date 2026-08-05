# Reuse last successful LLM findings (empty `--changed` pack)

**Status:** Approved 2026-08-05  
**Blog:** Outline parked in [docs/blog-ideas/reuse-last-llm-findings.md](../../blog-ideas/reuse-last-llm-findings.md) — expand later for CRC / product blog.

## Problem

With `--changed` and a warm fingerprint cache (`+0/~0/-0`), RepoLens correctly skips the LLM. The CLI then looked like a “clean” review (zeros / N/A) even when a prior deep LLM pass existed. Scanning `reports/` by newest file is wrong: skipped and scanners-only runs would win.

## Decisions

| Decision | Choice |
|----------|--------|
| Source of truth | Canonical snapshot in `.repolens/repolens.sqlite` `meta` after each **successful LLM** run |
| Which report | That snapshot — not newest `reports/*` |
| Bootstrap | If meta empty: newest `*.json` with `llmCompleted=true`; else **richest** `*.md` under `--out` (most findings — not newest empty skip) |
| Merge | Prior LLM issues/themes/coverage/scores + **this run’s** scanner findings (dedupe by file+line+title) |
| Confidence | `max(prior.confidence - 5, 40)` with durability note that AI findings were carried forward |
| Flags | `llmCompleted` on fresh LLM reports; `llmSkipped` + `llmReusedFrom` on reuse |

## Flow

1. Fresh LLM succeeds → persist report JSON + `saved_at` / model / mode in meta (`last_llm_*`).  
2. Empty `--changed` pack → load snapshot (or bootstrap) → merge scanners → write new report marked reused.  
3. No snapshot → keep skip path (scanners only + clear messaging).

## Non-goals

- Perfect round-trip of every markdown quirk (bootstrap is best-effort).  
- Treating scanners-only / dry-run / empty skip reports as “last LLM.”  
- Git-history blame of findings.
