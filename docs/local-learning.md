# Local learning (opt-in)

RepoLens can keep a **local** index of your repository to improve later reviews. Nothing is uploaded to a RepoLens service.

One **SQLite + FTS5** store (`.repolens/repolens.sqlite`) holds fingerprints and timings with no file contents, plus an opt-in `chunks` index after you accept local learning. 



## Enable

1. Consent (prints a plain-language notice):

```bash
repolens learn build --path . --accept-local-learning
```

2. Optionally set in config:

```toml
[local_learning]
enabled = true
cache_dir = ".repolens"
```

When `enabled = true` **and** consent exists, reviews prepend retrieved local chunks to the LLM prompt pack.

## Commands

| Command | Purpose |
|---------|---------|
| `repolens learn build --accept-local-learning` | Build/rebuild SQLite FTS index |
| `repolens learn status` | Consent + index presence |
| `repolens learn clear` | Clear the FTS chunks. Consent and the fingerprint/run rows stay. A leftover `index.sqlite` is removed only when the unified database is not there. |

## Where it runs

**Local-first:** adaptive fingerprints and FTS assume a normal local project checkout. The store needs a writable `.repolens/` directory on that machine.

## Storage (gitignored)

Under `.repolens/` (auto `.gitignore` `*`):

| File | Role |
|------|------|
| `consent.toml` | Informed consent record |
| `repolens.sqlite` | Unified store: fingerprints/runs + FTS5 `chunks` (Phase 5); legacy `index.sqlite` migrated on open |
| `memory.toml` | Dismissals / ignore path preferences |

## Optional embeddings

```bash
pip install "repolens-audit[local-ml]"
```

Keyword FTS works without this extra. The `[local-ml]` extra installs `sentence-transformers` for future vector enhancement; retrieval remains FTS-first in this alpha.

## CI

Local learning is **off** in the GitHub Action by default (ephemeral runners). Prefer durable project machines for indexes.

## Disable

- Set `local_learning.enabled = false`, or  
- Delete `.repolens/`
