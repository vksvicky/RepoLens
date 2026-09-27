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

### Supported platforms for `plugins install`

Pinned native downloads (gitleaks, osv-scanner) currently cover:

| OS | Architectures |
|----|----------------|
| macOS | arm64, amd64 |
| Linux | amd64, arm64 |
| Windows | **Not pinned yet** — put tools on `PATH` yourself, or run under [WSL](https://learn.microsoft.com/windows/wsl/) and use Linux steps |

Semgrep is installed via pip (`repolens-audit[scanners]` or `plugins install semgrep`) and usually works on all three platforms when Python supports it.

What the `[scanners]` **pip extra** contains (and that it is a RepoLens install option, not per-project config): [install-extras.md](./install-extras.md).  
Cross-OS CLI walkthrough: [try-on-your-repo.md](./try-on-your-repo.md).

## Tools

| Name | Role | Typical binary |
|------|------|----------------|
| `gitleaks` | Secrets in the working tree (`--no-git`) and in git history (commit log, all branches). History hits are P1 `sec.repo_hygiene_secrets`, separate from the `.gitignore` heuristic. The secret value is not copied into the report. | `gitleaks` |
| `semgrep` | SAST / pattern rules | `semgrep` (pip or cache venv) |
| `osv` | Dependency CVEs | `osv-scanner` |
| `trivy` | FS vulns + misconfig (+ secrets) | `trivy` (pinned archive) |
| `checkov` | IaC policy (Terraform/K8s/…) | `checkov` (pip cache venv) |

Default `enabled` remains gitleaks/semgrep/osv so missing Trivy/Checkov do not add noise. Opt in after install:

```bash
repolens plugins install trivy checkov --yes
# then set enabled = […, "trivy", "checkov"] or: --scanners gitleaks,semgrep,osv,trivy,checkov
```

## Config (`.repolens.toml` or user config)

```toml
[scanners]
enabled = ["gitleaks", "semgrep", "osv"]
# enabled = ["gitleaks", "semgrep", "osv", "trivy", "checkov"]
require = false
sbom = true       # CycloneDX (`sbom.cdx.json`) when Trivy is installed
licenses = true   # license IDs + notes from the SBOM
```

### SBOM / licenses (Phase 6.2)

When Trivy is on `PATH` or in the plugin cache (or requested via `--scanners …,trivy`), RepoLens writes a CycloneDX SBOM next to the report and adds a **Supply chain** section (Markdown + JSON `supplyChain`). OSV and Trivy CVE rows for the same advisory are deduped (OSV preferred). The LLM must not invent dependency graphs or reachability — see [FAQ](./faq.md#how-do-owasp--cve--security-audits-work).

## CLI flags

| Flag | Meaning |
|------|---------|
| `--scanners auto` | Run enabled tools that resolve (default when config enables them) |
| `--scanners off` | Skip scanners |
| `--scanners gitleaks,osv` | Run only these |
| `--require-scanners` | Exit 2 if an enabled/requested scanner is missing |
| `--scanners-only` | Skip LLM; report scanner results only |
| `--import-sarif PATH` | Merge findings from a SARIF 2.1 file (repeatable); `source=scanner`; tool run appears as `sarif:<driver>` in **Automated scanners** |
| `--require-sarif-import` | Exit **2** if any `--import-sarif` path is missing or unreadable (default: soft-fail) |

## Import third-party SARIF (CodeQL, Sonar, ESLint, …)

RepoLens does **not** replace your existing SAST fleet. When CodeQL, SonarQube, ESLint, or another tool already emits SARIF 2.1, merge those rows into the same gate report instead of maintaining a parallel shell pipeline:

```bash
TARGET=/path/to/your-repo
repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only \
  --import-sarif "$TARGET/codeql.sarif" \
  --import-sarif "$TARGET/eslint.sarif" \
  --require-sarif-import \
  --fail-on HIGH
```

- Repeat `--import-sarif` for each file; dialect-tolerant parsing (per-run driver name → `sarif:ESLint`, `sarif:CodeQL`, …).
- Imported rows use `source=scanner` and participate in **`--fail-on`** like native gitleaks/semgrep output.
- **`--fail-on`** is the **machine gate** (exit code 1). **`--format md`**, JSON, PDF/export, and LLM narrative are **reporting** — add `--format md` or `--format both` when you want an executive Markdown pack; they do not change the gate by themselves.
- **`--require-sarif-import`** makes missing/unreadable SARIF paths a hard CI failure (exit 2).

Companion CI pattern (run upstream SARIF first, then RepoLens):

```bash
# After CodeQL / Sonar / ESLint steps write SARIF artifacts:
repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only \
  --import-sarif "$TARGET/codeql.sarif" \
  --import-sarif "$TARGET/eslint.sarif" \
  --require-sarif-import \
  --format both --fail-on HIGH
```

Copy-paste recipes for Sonar, Qodana, Brakeman, PMD, and Bearer: [ci.md companion recipes](./ci.md#companion-recipes-sonar--qodana--brakeman--pmd--bearer).  
See also [ci.md import gate](./ci.md#import-external-sarif-companion-gate) · export (outbound) SARIF: [faq](./faq.md#does-repolens-export-sarif-for-github--sonar).

## Cache location

Pinned installs land under `~/.cache/repolens/tools/` (or `$XDG_CACHE_HOME/repolens/tools/`).

Downloads use HTTPS from upstream GitHub release URLs pinned in `src/repolens/plugins.py`, with **SHA-256 verification** for gitleaks/OSV binaries. Archives are extracted with path-traversal checks. Prefer `--yes` only in trusted CI. Semgrep installs via pip with a pinned version (`semgrep==…`).

## Semgrep config / offline

Default Semgrep config is `auto` (may download rules). For CI or air-gapped hosts:

```bash
export REPOLENS_SEMGREP_CONFIG=./.semgrep.yml   # or a local rules directory
# or a previously cached ruleset path Semgrep understands
repolens review --path . --scanners semgrep
```

## Related

- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) — Option C checklist  
- [design/phase-3-scanners.md](./design/phase-3-scanners.md)  
- [design/repolens-vs-appsec-tools.md](./design/repolens-vs-appsec-tools.md) — honest comparison vs Checkmarx, Snyk, CodeQL, Trivy, …  
- [ci.md](./ci.md) — GitHub Action  

