# Try RepoLens on a local repository

Use these steps to review **any project folder on your machine** before relying on PyPI or CI.

Replace `[username]` with your macOS/Linux username (or adjust the paths for your layout). Replace `[your-project]` with the folder name of the repo you want reviewed.

## 1) Install RepoLens from a clone

```bash
cd /Users/[username]/Development/RepoLens
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
repolens version
```

On Linux the home path is often `/home/[username]/…` instead of `/Users/[username]/…`.

## 2) Point `--path` at the repo to review

```bash
# Keep the RepoLens venv active, then:
TARGET=/Users/[username]/Development/[your-project]

# Inventory only (no LLM, no scanners)
repolens review --path "$TARGET" --out "$TARGET/reports" --dry-run

# Optional: install scanners once on this machine
repolens plugins install all --yes
repolens plugins status

# Deterministic scanners only (no API key required)
repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only --fail-on ""

# Full review (needs `repolens init` + cloud key or Ollama)
repolens review --path "$TARGET" --out "$TARGET/reports"
repolens sentinel --path "$TARGET" --out "$TARGET/reports"
```

Open the Markdown under `$TARGET/reports/gate_review_report_YYYY-MM-DD.md`.

## 3) Review the RepoLens repo itself (dogfood)

```bash
cd /Users/[username]/Development/RepoLens
source .venv/bin/activate

repolens review --path . --out ./reports-dogfood --dry-run
repolens plugins install all --yes
repolens review --path . --out ./reports-dogfood --scanners-only --fail-on ""
```

`reports-dogfood/` is gitignored. Pass criteria for a pre-publish check are in [publishing.md](./publishing.md#pre-publish-dogfood).

## 4) Tips

| Goal | Flag / note |
|------|-------------|
| Current directory | Omit `--path` or use `--path .` |
| No LLM key | Use `--dry-run` or `--scanners-only` |
| Fail CI-style on High+ | `--fail-on HIGH` |
| Semgrep offline / custom rules | `export REPOLENS_SEMGREP_CONFIG=./.semgrep.yml` |
| Remote instead of local | `--github OWNER/REPO` — see [remote-sources.md](./remote-sources.md) |

Setup for AI providers: [setup-ai-and-scanners.md](./setup-ai-and-scanners.md).  
Scanners detail: [scanners.md](./scanners.md).  
CI Action: [ci.md](./ci.md).
