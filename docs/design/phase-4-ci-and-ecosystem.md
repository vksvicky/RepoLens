# Design: Phase 4 — CI & ecosystem

**Status:** Implemented 2026-08-04  
**Related:** [phases.md](../phases.md) · [ai-keys-scanners-and-local-learning.md](./ai-keys-scanners-and-local-learning.md) · [phase-3-scanners.md](./phase-3-scanners.md)

## Decisions

| Topic | Choice |
|-------|--------|
| Scope | Full Phase 4 checklist in one pass (Option C) |
| Delivery | Layered verticals / ordered commits (Approach 2) |
| Local learning | Real opt-in index + memory (not stub-only) |
| Index stack | Keyword/TF-IDF always when enabled; embeddings only with `repolens[local-ml]` |
| Action default | `run=auto`: scanners always; LLM if API key env present; `dry-run` as explicit input |
| PyPI | Real alpha publish via Trusted Publishing (OIDC) |
| Action packaging | Root `action.yml` for `uses:` **and** example workflow |
| Local learning in CI | Off by default (ephemeral runners) |
| Bitbucket | Documented script in `docs/ci.md` (no marketplace Pipe this pass) |

## Architecture

```text
Consumer CI
  └─ uses: vksvicky/RepoLens@vX  (action.yml)
        ├─ setup-python + pip install repolens[scanners]==version
        ├─ optional: plugins install --yes
        ├─ run: dry-run | auto (scanners + optional LLM) | scanners-only | llm
        └─ upload reports/ artifact (example workflow)

Release
  └─ tag v0.1.0a1 → Trusted Publishing → PyPI

Local learning (opt-in; not Action default)
  └─ .repolens/index.sqlite (keyword/TF-IDF)
  └─ optional embeddings if [local-ml]
  └─ .repolens/memory.toml
  └─ consent gate → retrieve top chunks → enrich LLM context pack
```

## Slice order (Approach 2)

1. **Action + CI docs** — `action.yml`, example workflow, `docs/ci.md`  
2. **Publish** — release workflow, `docs/publishing.md`, README install from PyPI  
3. **Local learning** — consent, index, memory, CLI, `docs/local-learning.md`, wire into pipeline  
4. **Polish** — Bitbucket script section, `examples/monorepo/`, confidence-log helper/template, FAQ/phases/CHANGELOG

## GitHub Action

**Files:** `/action.yml` (composite) · `.github/workflows/repolens-example.yml`

| Input | Default | Meaning |
|-------|---------|---------|
| `path` | `.` | Project root |
| `mode` | `review` | `review` \| `sentinel` \| `architecture` |
| `run` | `auto` | `auto` = scanners always; LLM if known API key env set · `dry-run` · `scanners-only` · `llm` (fail if no key) |
| `fail-on` | `HIGH` | Empty string disables |
| `scanners` | `auto` | CLI `--scanners` |
| `require-scanners` | `false` | |
| `version` | `0.1.0a1` | `pip install repolens[scanners]==…` |
| `install-plugins` | `true` | `repolens plugins install all --yes` |

**Secrets / env (optional):** `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`.  
**Example workflow:** checkout → Action → upload `reports/` artifact.  
**Exit mapping:** CLI 1 (`fail-on`) and 2/3/4 fail the job with logged reason.

**Bitbucket:** shell script example in `docs/ci.md` mirroring Action steps (pip install, plugins, `repolens review`).

## Local learning

| Piece | Behaviour |
|-------|-----------|
| Default | Off |
| Enable | `local_learning.enabled = true` **and** `--accept-local-learning` or interactive yes |
| Notice | Existing copy in [ai-keys-scanners-and-local-learning.md](./ai-keys-scanners-and-local-learning.md) §4 |
| Storage | `.repolens/index.sqlite`, `.repolens/memory.toml` (document in `.gitignore` examples) |
| Index | Keyword/TF-IDF always; embeddings iff `repolens[local-ml]` |
| Use | Retrieve top‑N chunks into context pack before LLM |
| CLI | `repolens learn build\|status\|clear` (+ review uses index when enabled) |
| CI | Not enabled by Action defaults |
| Cloud LLM | Consent still discloses excerpts may leave the machine |

**Extra:** `repolens[local-ml]` optional dependency (e.g. `sentence-transformers` or equivalent small stack) — keyword path must work without it.

## PyPI / publishing

- Workflow on `v*` tags: build → Trusted Publisher upload to PyPI  
- First publish: `0.1.0a1` (match `pyproject.toml`)  
- `docs/publishing.md`: one-time PyPI project + Trusted Publisher configuration (manual UI steps)  
- Action documents git-tag install fallback if PyPI unavailable

## Docs & polish deliverables

| Artifact | Purpose |
|----------|---------|
| `docs/ci.md` | Action + Bitbucket script |
| `docs/publishing.md` | Release / PyPI |
| `docs/local-learning.md` | Consent, storage, commands |
| `examples/monorepo/` | Sample config + path notes |
| `docs/review-confidence-log.md` | Template; optional tiny `repolens confidence append` helper |
| FAQ / phases / README / CHANGELOG | Reflect shipped Phase 4 |

## Error handling

| Case | Behaviour |
|------|-----------|
| `run=llm` and no key | Exit 2 + setup hint |
| `run=auto` and no key | Scanners only (success unless fail-on / require-scanners) |
| Enable learning without consent | Refuse; print notice |
| Publish failure | Release job fails; consumers use git install fallback |

## Testing

- Local learning: TDD for consent gate, index build, retrieval, memory load  
- Action: keep composite thin; cover CLI flag assembly with unit tests where practical  
- This repo’s CI: continue pytest/ruff; do **not** require paid LLM calls in default CI  
- Publish workflow: validate YAML; first real upload on tagged release after Trusted Publisher is configured

## Non-goals (this pass)

- Bitbucket Pipe marketplace listing  
- Web UI / SaaS  
- Silent or cloud local learning  
- Replacing CodeQL/Dependabot/Snyk  
- Guaranteeing PyPI upload without operator Trusted Publisher setup (docs must list the manual step)

## Exit criteria (from phases.md)

- [x] Documented CI example (`docs/ci.md` + Action)  
- [x] Published install path (publish workflow + docs; git/Action `local` install; PyPI upload after Trusted Publisher setup)  
- [x] Local-learning implemented (not deferred) with accurate FAQ  
