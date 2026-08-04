# Remote sources (Phase 2)

Review a repository that is **not** already on disk. RepoLens shallow-clones into a temp directory, runs the same review pipeline as `--path`, writes reports under your **current working directory** `./reports/` (unless `--out`), then deletes the clone.

Use **exactly one** source: `--path`, `--git-url`, `--github`, `--bitbucket`, or `--hf`.

Walkthrough with OS paths + placeholders: [try-on-your-repo.md](./try-on-your-repo.md#3-review-a-remote-github-bitbucket-hugging-face-git-url).

## Commands by source

Placeholders: `[owner]`, `[repo]`, `[workspace]`, `[org]`, `[name]`. Example user/project: `jackfrost` / `acme-api`.

### Local folder (`--path`)

```bash
repolens review --path ./[your-project] --dry-run
repolens review --path /Users/[username]/Development/[your-project] --scanners-only
repolens review --path . --dry-run

# Example: repolens review --path /Users/jackfrost/Development/acme-api --dry-run
```

### GitHub (`--github`)

```bash
repolens review --github [owner]/[repo]
repolens review --github [owner]/[repo] --ref main --dry-run
repolens review --github [owner]/[repo] --ref main --scanners-only --fail-on ""
repolens sentinel --github [owner]/[repo] --ref main

# Example: repolens review --github jackfrost/acme-api --ref main --dry-run
```

### Bitbucket (`--bitbucket`)

```bash
repolens review --bitbucket [workspace]/[repo]
repolens review --bitbucket [workspace]/[repo] --ref main --dry-run
repolens review --bitbucket [workspace]/[repo] --ref main --scanners-only --fail-on ""

# Example: repolens review --bitbucket jackfrost/acme-api --ref main --dry-run
```

### Hugging Face Hub (`--hf`)

```bash
# Model git repo
repolens review --hf [org]/[name] --dry-run

# Dataset or Space (prefix required)
repolens review --hf datasets/[org]/[name] --dry-run
repolens review --hf spaces/[org]/[name] --ref main --dry-run

# Example:
# repolens review --hf jackfrost/acme-model --dry-run
# repolens review --hf datasets/jackfrost/acme-data --dry-run
```

### Any git URL (`--git-url`)

```bash
repolens review --git-url https://github.com/[owner]/[repo].git --ref main --dry-run
repolens review --git-url https://gitlab.com/[owner]/[repo].git --ref v1.2.0
repolens review --git-url https://bitbucket.org/[workspace]/[repo].git --ref main
repolens review --git-url git@github.com:[owner]/[repo].git

# Example: repolens review --git-url https://github.com/jackfrost/acme-api.git --ref main --dry-run
```

## Authentication (private remotes)

| Forge | Env vars (first match wins where listed) | Notes |
|-------|------------------------------------------|--------|
| GitHub | `GITHUB_TOKEN` or `GH_TOKEN`, else `gh auth token` | Public clones work anonymously |
| Bitbucket | `BITBUCKET_TOKEN` or `BITBUCKET_APP_PASSWORD` | App passwords: also set `BITBUCKET_USERNAME` |
| Hugging Face | `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN` | Needed for private Hub repos |
| Generic HTTPS git | Depends on host (same tokens as above when URL matches) | Prefer tokens in env, not in the URL |

**Never** put tokens in the git URL, commit them, or paste them into shared shell history. RepoLens passes tokens via git HTTP extra headers when possible so they do not appear in the clone URL.

Configure preferred env var names in [`.repolens.example.toml`](../.repolens.example.toml) under `[sources]` where applicable.

Private clone failures typically exit with code **3**.

## Reports

| Source | Default report directory |
|--------|---------------------------|
| `--path ./my-app` | `./my-app/reports/` (or project `report_dir`) |
| `--github` / `--bitbucket` / `--hf` / `--git-url` | `./reports/` under **cwd** |
| Any | `--out DIR` overrides |

## Requirements

- `git` on `PATH`
- Network access to the forge
- For private repos: the matching token (table above)

## Related

- [try-on-your-repo.md](./try-on-your-repo.md) — install + local/remote examples  
- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) — LLM provider setup  
- [design/phase-2-multi-source-ingest.md](./design/phase-2-multi-source-ingest.md) — design decisions  
- [faq.md](./faq.md#hosting-sources-phase-2) — hosting matrix  
