# Phase 5 — Adaptive fingerprint cache, progressive review, configurable recommendations

**Status:** Design approved (Approach 1 + A+C; **unified SQLite + FTS5** — no JSON fingerprint layer)  
**Date:** 2026-08-01
**Depends on:** Phase 4 local learning (FTS5), Phase 1 inventory/LLM pipeline

## 1. Problem

Users (and ScoreVault-scale repos) hit opaque LLM timeouts and long silent waits. Timeouts differ **per project** and must not be a single hard-coded global. RepoLens should:

1. **Learn** runtime characteristics of each project locally.  
2. **Recommend** timeout / scope for the next run (still fully overridable).  
3. **Progressively** update a cache when files are added / changed / deleted, then scan/review accordingly.  
4. Keep **content** learning opt-in (consent); keep a lighter **fingerprint** layer always available for metrics.

## 2. Decisions (locked)

| Decision | Choice |
|----------|--------|
| Architecture | **One SQLite database** under `.repolens/` — fingerprints, run metrics, and **FTS5** content chunks together |
| Content / FTS5 | **Opt-in** — `chunks` virtual table filled only after `repolens learn` consent (**A**) |
| Fingerprint + run metrics | **Always-on** — `files` / `runs` / `meta` tables; **no file contents** (**C**) |
| Why not JSON for fingerprints | Avoid a later migrate to SQLite; FTS5 already requires SQLite; one store keeps progressive FTS updates in the same transaction as fingerprint sync |
| Feature slice | Progressive cache + incremental review first; timeout via heuristics → measured runs |
| Overrides | CLI / env / project config **always win** over recommendations |

## 3. Data model

### 3.1 Unified store — `.repolens/repolens.sqlite`

Schema version in `meta`. On open: `CREATE TABLE IF NOT EXISTS` for all structural tables; create FTS5 `chunks` if missing.

| Object | Role | Contents? |
|--------|------|-----------|
| `files` | Fingerprints: `path PRIMARY KEY`, `sha256`, `size`, `mtime_ns`, `priority_band`, `updated_at` | **No** |
| `runs` | Run metrics: timing, mode, provider, model, `files_in_prompt`, `llm_seconds`, `timeout_used`, `outcome` | **No** |
| `meta` | `key` / `value`: `schema_version`, `recommended_timeout_seconds`, `last_full_review_at`, … | **No** |
| `chunks` | FTS5 `(path, content)` — same role as today’s learning index | **Yes** (opt-in only) |

**Compatibility:** If a project already has Phase 4 `index.sqlite` (FTS-only), open/migrate into `repolens.sqlite` once (copy `chunks` rows, then prefer the unified file). New projects only create `repolens.sqlite`.

Directory `.repolens/` stays gitignored.

### 3.2 Consent boundary

| Without consent | With consent (`learn build --accept-local-learning`) |
|-----------------|------------------------------------------------------|
| `files` / `runs` / `meta` may be written | Same + upsert/delete `chunks` for paths |
| FTS queries return empty | FTS retrieval works as today |

### 3.3 Config

```toml
[adaptive]
enabled = true           # fingerprint cache; set false to disable
mode = "auto"            # auto | full | changed
timeout_margin = 1.3
min_timeout_seconds = 120
max_timeout_seconds = 3600

[model]
# timeout_seconds = 1800   # explicit override — never overwritten silently
```

**Timeout resolution order:**

1. CLI `--timeout`  
2. `REPOLENS_TIMEOUT`  
3. Explicit `[model].timeout_seconds`  
4. `meta.recommended_timeout_seconds` (if adaptive enabled + history)  
5. Provider default (Ollama 900s, cloud 120s)

## 4. Review flow

### 4.1 Cold cache

1. Inventory → write/replace `files` rows (hashes).  
2. Heuristic ETA/timeout → progress UI.  
3. Scanners + **full** LLM pack (existing caps).  
4. Insert `runs` row; update recommended timeout in `meta`.  
5. If consented → upsert FTS `chunks` for those paths.

### 4.2 Warm cache

1. Rescan → **added / changed / deleted** vs `files`.  
2. Update `files`; progress summary.  
3. `adaptive.mode=auto`: LLM pack = changed + P1-band (+ small context).  
4. `--full` / `mode=full` → full pack; `mode=changed` → changed/added only.  
5. Recompute recommended timeout from last N successful `runs` (p95 × margin, clamped).  
6. If consented → incremental FTS upsert/delete for touched paths only.

### 4.3 Scanners

Default full-tree. Optional later: `adaptive.scanners = "full" | "changed"`.

## 5. Recommendations (“ML” pragmatic)

| Signal | Use |
|--------|-----|
| File count / prompt size | Cold-start timeout / ETA |
| Measured `llm_seconds` | Warm recommended timeout |
| Change set size | Progress + pack selection |
| FTS5 (+ optional embeddings) | Opt-in prompt context (existing) |

Local only; never uploaded to RepoLens.

## 6. CLI / UX

| Surface | Behavior |
|---------|----------|
| Progress | Cache sync, ETA, applied timeout, LLM heartbeat |
| `--verbose` | Bucket counts; recommended vs overridden timeout |
| `--full` | Force full LLM pack |
| `--timeout N` | Override |
| `repolens adaptive status` | Recommended timeout, last run, change dry-run |
| `repolens learn *` | Unchanged consent UX; writes into unified DB |

## 7. Privacy

| Data | Always-on | Opt-in FTS |
|------|-----------|------------|
| Paths / hashes / sizes / timings | Yes | Yes |
| Source contents | **No** | Yes, after consent |

## 8. Deployment model: local first, network later

| Now (MVP) | Later |
|-----------|--------|
| Run RepoLens **on the machine that has the project** (local disk) | Optional review of repos on a **network path** / shared volume |
| `.repolens/repolens.sqlite` on local disk next to the project | Same layout, but path may be SMB/NFS/etc. |
| Assume reliable local FS for SQLite writes | Require **read-write** on the project root (or a configured cache dir) before enabling adaptive/FTS on network paths; document locking / “don’t use flaky shares” |

**Policy for a future network-path mode:**

1. Detect or declare `sources.network_path = true` (or similar).  
2. Verify the process can **create/update** `.repolens/` (write probe).  
3. If only read-only: allow `--dry-run` / scanners that need read-only, but **disable** fingerprint/FTS writes (or redirect cache to a local `adaptive.cache_dir`).  
4. Warn that SQLite on some network filesystems is unsupported or unsafe; prefer local cache dir with the repo mounted read-only.

Until that lands, docs and UX assume **local checkout**.

## 9. Non-goals (MVP)

- Central training  
- Exact ETA guarantees  
- JSON fingerprint format  
- Network/SMB repo paths as a first-class supported mode (deferred — see §8)  
- Windows native plugin install (orthogonal)

## 10. Implementation sketch

1. Unified SQLite schema + open/migrate from `index.sqlite` + tests. *(done foundation)*  
2. Fingerprint sync + change classification + timeout recommendation helpers. *(done foundation)*  
3. Wire `run_review` (pack selection + timeout + record run).  
4. Incremental FTS upsert/delete when consented; keep `learn build` as full rebuild.  
5. `adaptive status` + config + docs.  
6. *(Later)* Network-path write probe + optional local `cache_dir` redirect.

## 11. Success criteria

- Warm `auto` review sends a smaller LLM pack after small edits.  
- Recommended timeout is per-project and overridable.  
- No content in DB without consent.  
- `[adaptive] enabled = false` restores prior behavior.  
- No JSON→SQLite migration path required.

## 12. Related docs

- [local-learning.md](../local-learning.md)  
- [ai-keys-scanners-and-local-learning.md](./ai-keys-scanners-and-local-learning.md)  
- [phase-4-ci-and-ecosystem.md](./phase-4-ci-and-ecosystem.md)  
