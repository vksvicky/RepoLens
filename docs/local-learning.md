# Local learning (opt-in)

RepoLens can keep a **local** index of your repository to improve later reviews. Nothing is uploaded to a RepoLens service.

**Related (not shipped yet):** Phase 5 uses one **SQLite + FTS5** store (`.repolens/repolens.sqlite`): always-on fingerprints/timings (no contents) + the same opt-in `chunks` FTS index. 



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
| `repolens learn clear` | Delete `index.sqlite` (keeps consent) |

## Where it runs

**Local-first:** adaptive fingerprints and FTS assume a normal local project checkout. Network/SMB paths may come later and will need **read-write** access to create `.repolens/` (or a local cache redirect).  §8.

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
