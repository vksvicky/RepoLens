# Remote sources (Phase 2)

Review a repository that is **not** already on disk. RepoLens shallow-clones into a temp directory, runs the same review pipeline as `--path`, writes reports under your **current working directory** `./reports/` (unless `--out`), then deletes the clone.

## Commands

```bash
# GitHub
repolens review --github owner/repo
repolens review --github owner/repo --ref main --dry-run

# Bitbucket
repolens review --bitbucket workspace/repo --ref main

# Hugging Face Hub (model / dataset / space git repos)
repolens review --hf org/model
repolens review --hf datasets/org/dataset-name
repolens review --hf spaces/org/space-name

# Any git URL (HTTPS or SSH)
repolens review --git-url https://github.com/owner/repo.git --ref v1.2.0
repolens review --git-url git@github.com:owner/repo.git
```

Use **exactly one** source: `--path`, `--git-url`, `--github`, `--bitbucket`, or `--hf`.

## Authentication (private GitHub)

Order:

1. Environment: `GITHUB_TOKEN` or `GH_TOKEN`  
2. Else, if [GitHub CLI](https://cli.github.com/) is installed and logged in: `gh auth token`  
3. Else public clones work anonymously; private clones fail with exit code **3**

Configure the env var name in `.repolens.example.toml` under `[sources]` (`github_token_env`).

**Never** put tokens in the git URL, commit them, or pass them on a shell history line you will share. RepoLens passes the token via git HTTP extra headers when possible so it does not appear in the clone URL.

## Reports

| Source | Default report directory |
|--------|---------------------------|
| `--path ./my-app` | `./my-app/reports/` (or project `report_dir`) |
| `--github` / `--git-url` | `./reports/` under **cwd** |
| Any | `--out DIR` overrides |

## Requirements

- `git` on `PATH`
- Network access to the forge
- For private GitHub: token or `gh auth login`

## Related

- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) — LLM provider setup  
- [design/phase-2-multi-source-ingest.md](./design/phase-2-multi-source-ingest.md) — design decisions  
- [faq.md](./faq.md#hosting-sources-phase-2) — hosting matrix  
