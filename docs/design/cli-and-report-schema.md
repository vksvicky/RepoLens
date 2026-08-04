# Design: CLI UX & report schema

**Status:** Approved; Phases 1–4 implemented (2026-08-04)  
**Implements in:** Phase 1+ (local, remotes, scanners, CI Action, local learning)  
**CLI language:** Python 3.11+ (see [Decision](#decision-cli-implementation-language))  
**Runtime topology (diagrams):** [ADR-01](../adr/01_analysis_runtime_architecture.md) · [legend](../adr/_diagram_legend.md)

---

## Decision: CLI implementation language

| Option | Pros | Cons |
|--------|------|------|
| **Python 3.11+** ★ | Excellent CLI ergonomics (`typer`/`click`), strong security-scanner ecosystem, Hugging Face / data-science familiarity, easy packaging via `pipx`/`uv` | Heavier runtime than a static binary |
| TypeScript (Node/Bun) | Fast iteration if UI added later; Octokit-native | Weaker fit for wrapping Semgrep/OSV/gitleaks; dual ecosystem for “security CLI” audience |

**Choice: Python 3.11+**, packaged as console script `repolens`. PyPI via Trusted Publishing; optional later PyInstaller/uvx binaries.

Stack:

| Concern | Library |
|---------|-------------------|
| CLI | `typer` + `rich` (implemented) |
| Config | `tomllib` / `pydantic-settings` |
| HTTP / Git hosts | `httpx`, `GitPython` or subprocess `git` |
| Tests | `pytest` |
| Lint/types | `ruff`, `mypy` |

---

## Commands (UX)

```text
repolens review [options]       # Full P1→P2→P3
repolens sentinel [options]     # Security-only (P1)
repolens architecture [options] # Architecture playbook (full or scoped)
repolens export <report.md>     # Convert / republish (PDF if pandoc available)
repolens version
```

### Common options

| Option | Purpose |
|--------|---------|
| `--path PATH` | Local project root (default: `.`) |
| `--git-url URL` | Clone then review (Phase 2 MVP) |
| `--github OWNER/REPO` | GitHub shortcut (Phase 2 MVP) |
| `--bitbucket WORKSPACE/REPO` | Bitbucket shortcut (Phase 2) |
| `--hf ID` | Hugging Face Hub git repo (Phase 2) |
| `--ref REF` | Branch/tag/commit for remotes |
| `--mode full\|diff` | Whole tree vs git diff / since-ref |
| `--since REF` | Diff base for `--mode diff` |
| `--out DIR` | Report directory (default: `reports/`) |
| `--format md\|json` | Artifact format (`md` required in Phase 1) |
| `--model NAME` | Override configured model |
| `--fail-on SEVERITY` | Exit non-zero if findings ≥ severity (CI) |
| `--dry-run` | Resolve sources + file list; no LLM call |
| `--trust-project-config` | Allow project `.repolens.toml` to set provider/base_url/api_key_env |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (and no `--fail-on` breach) |
| 1 | Findings at/above `--fail-on` |
| 2 | Usage / config error |
| 3 | Source fetch / auth failure |
| 4 | Model / provider failure |

---

## Review pipeline

```text
Source resolve → File inventory (ignores + P1 prioritization)
    → Pack context (playbooks + files/diff)
    → LLM analyze (structured JSON)
    → Validate schema (require codeExample for Critical/High)
    → Write Markdown (+ optional JSON)
    → Print summary (confidence %, counts, top issues)
```

Playbooks loaded from package data / repo `playbooks/`:

- `sentinel` / P1 → `playbooks/security.md`
- `architecture` → `playbooks/architecture.md`
- `review` → security then reliability pass then architecture (scoped unless `--full-audit`)

---

## Finding schema (canonical)

JSON shape produced by the model and normalized by the CLI:

```json
{
  "schemaVersion": "1.0",
  "confidence": 82,
  "summary": {
    "critical": 0,
    "high": 1,
    "medium": 3,
    "low": 2
  },
  "issues": [
    {
      "severity": "HIGH",
      "priority": "P1",
      "category": "Authentication",
      "file": "src/auth.py",
      "line": 42,
      "title": "Missing authorization check on admin route",
      "explanation": "Natural language why this matters here.",
      "impact": "Any authenticated user can call admin actions.",
      "recommendedFix": "Step-by-step remediation.",
      "codeExample": "def admin():\n    require_role('admin')\n    ...",
      "fixTiming": "immediately"
    }
  ],
  "durabilityGaps": ["tests", "ci", "secret-scanning"],
  "scores": null
}
```

### Validation rules

- `severity` ∈ `CRITICAL|HIGH|MEDIUM|LOW`
- `priority` ∈ `P1|P2|P3`
- Critical/High **must** have non-empty `codeExample` and `impact` (reject or re-prompt once)
- `confidence` integer 0–100
- `scores` object only for full architecture audits (1–10 dimensions)

### Markdown report

Filename: `gate_review_report_YYYY-MM-DD.md` (optionally `_<shortsha>.md`)

Sections: Gate verdict → P1 → P2 → P3 → Plan to fix → Durability gaps → (optional) Architecture scores.

---

## Config

Search order:

1. CLI flags  
2. `./.repolens.toml`  
3. `~/.config/repolens/config.toml`  
4. Environment variables (`REPOLens_*` / provider-specific)

See [`.repolens.example.toml`](../../.repolens.example.toml).

Secrets: API keys via env only; never write keys into reports. Untrusted project TOML cannot set `provider` / `base_url` / `api_key_env` unless `--trust-project-config`.

---

## Target languages & tools (product support)

RepoLens reviews **repositories**, not a single language runtime. Support tiers and FAQ: [../faq.md](../faq.md).

---

## Non-goals (Phase 1)

- GUI / web app  
- Auto-commit / auto-push  
- Bundling Semgrep/gitleaks as required dependencies (optional Phase 3 plugins instead)
