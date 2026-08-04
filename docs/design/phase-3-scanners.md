# Design: Phase 3 — Optional scanner plugins

**Status:** Implemented 2026-08-04  
**Related:** [ai-keys-scanners-and-local-learning.md](./ai-keys-scanners-and-local-learning.md) · [scanners.md](../scanners.md)

## Modules

| Path | Role |
|------|------|
| `src/repolens/scanners/` | Adapters + runner |
| `src/repolens/plugins.py` | `plugins install|status` (consent download) |
| `src/repolens/pipeline.py` | Merge scanner findings; `--scanners-only` |

## Decisions

| Topic | Choice |
|-------|--------|
| Packaging | Slim wheel; binaries via `repolens plugins install` + optional `repolens[scanners]` meta extra |
| Install UX | Consent prompt before download; `--yes` for CI |
| User says no | Manual install hints; PATH tools still used; LLM review continues |
| Tools (MVP) | gitleaks, Semgrep, OSV-Scanner |
| Resolve order | `PATH` → `~/.cache/repolens/tools/<name>/` |
| Require | `--require-scanners` / config `require=true` → exit 2 if enabled tool missing |

## Pipeline

```text
inventory → (optional) run scanners → LLM analyse → merge report
```

`--scanners-only` skips LLM and writes scanner findings + durability gaps only.

## Report

New Markdown section **Automated scanners**: per-tool status (ran / skipped / failed) and findings. Findings also appear as Issues (P1) when severity maps cleanly.
