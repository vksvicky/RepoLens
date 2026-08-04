# Design: Phase 2 — Multi-source ingest (MVP)

**Status:** Approved 2026-08-04  
**MVP scope:** `--git-url` + `--github` (Bitbucket / Hugging Face deferred)  
**Implements:** ADR-01 `SourceResolver`; CLI flags in [cli-and-report-schema.md](./cli-and-report-schema.md)

## Decisions

| Topic | Choice |
|-------|--------|
| Sources in MVP | Generic `--git-url` + `--github OWNER/REPO` |
| Auth (GitHub private) | `GITHUB_TOKEN` / `GH_TOKEN` env, else `gh auth token` |
| Reports for remotes | `./reports` under **cwd** (unless `--out`) |
| Clone strategy | Shallow (`--depth 1`); optional `--ref`; temp worktree; always cleanup |
| Token hygiene | Prefer `http.extraHeader` / git config env — **never** embed token in clone URL or logs |
| Mutual exclusion | Exactly one of `--path` (default `.`), `--git-url`, `--github` |

## CLI

```text
repolens review --github owner/repo [--ref REF] [--out DIR] ...
repolens review --git-url https://github.com/owner/repo.git [--ref REF] ...
repolens sentinel --github owner/repo --dry-run
```

| Exit | Meaning |
|------|---------|
| 2 | Usage (multiple sources, bad slug) |
| 3 | Clone / auth / fetch failure |

## Pipeline

```text
pick source → resolve (local | shallow clone) → inventory → pack → LLM → report → cleanup temp
```

- Local: config from project root; reports under project `report_dir`.
- Remote: model config from user/env only (project TOML in clone is still sanitized unless `--trust-project-config`); reports under `cwd/reports`.

## Deferred (Phase 2.1)

- `--bitbucket WORKSPACE/REPO`
- `--hf ID`
- Persistent worktrees / `--keep-clone`

## Auth docs

See [remote-sources.md](../remote-sources.md).
