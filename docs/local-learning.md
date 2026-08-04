# Local learning (opt-in)

RepoLens can keep a **local** index of your repository to improve later reviews. Nothing is uploaded to a RepoLens service.

Design: [design/ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md) · [design/phase-4-ci-and-ecosystem.md](./design/phase-4-ci-and-ecosystem.md)

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

## Storage (gitignored)

Under `.repolens/` (auto `.gitignore` `*`):

| File | Role |
|------|------|
| `consent.toml` | Informed consent record |
| `index.sqlite` | Keyword / FTS5 index |
| `memory.toml` | Dismissals / ignore path preferences |

## Optional embeddings

```bash
pip install "repolens[local-ml]"
```

Keyword FTS works without this extra. The `[local-ml]` extra installs `sentence-transformers` for future vector enhancement; retrieval remains FTS-first in this alpha.

## CI

Local learning is **off** in the GitHub Action by default (ephemeral runners). Prefer durable project machines for indexes.

## Disable

- Set `local_learning.enabled = false`, or  
- Delete `.repolens/`
