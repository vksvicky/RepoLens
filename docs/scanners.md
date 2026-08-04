# Optional scanners (Phase 3)

RepoLens can merge **deterministic** tool output into the same gate report. Scanners are **optional** — missing tools never stop an LLM review unless you pass `--require-scanners`.

## Quick start

```bash
# See what is available (PATH + cache)
repolens plugins status

# Download pinned binaries (prompts for consent; use --yes in CI)
repolens plugins install all
repolens plugins install gitleaks semgrep osv --yes

# Run a review that includes scanners when present
repolens review --path . --dry-run   # inventory only
repolens review --path . --scanners auto

# Scanners only (no LLM)
repolens review --path . --scanners-only
```

If you decline a download, RepoLens prints manual install hints and still uses any matching tool already on your `PATH`.

## Tools

| Name | Role | Typical binary |
|------|------|----------------|
| `gitleaks` | Secrets | `gitleaks` |
| `semgrep` | SAST / pattern rules | `semgrep` (pip or cache venv) |
| `osv` | Dependency CVEs | `osv-scanner` |

## Config (`.repolens.toml` or user config)

```toml
[scanners]
enabled = ["gitleaks", "semgrep", "osv"]
require = false
```

## CLI flags

| Flag | Meaning |
|------|---------|
| `--scanners auto` | Run enabled tools that resolve (default when config enables them) |
| `--scanners off` | Skip scanners |
| `--scanners gitleaks,osv` | Run only these |
| `--require-scanners` | Exit 2 if an enabled/requested scanner is missing |
| `--scanners-only` | Skip LLM; report scanner results only |

## Cache location

Pinned installs land under `~/.cache/repolens/tools/` (or `$XDG_CACHE_HOME/repolens/tools/`).

Downloads use HTTPS from the upstream GitHub release URLs pinned in `src/repolens/plugins.py`. Archives are extracted with path-traversal checks. Prefer `--yes` only in trusted CI.

## Related

- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) — Option C checklist  
- [design/phase-3-scanners.md](./design/phase-3-scanners.md)
