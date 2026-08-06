# RepoLens

**See into any repository—security, reliability, and architecture—before you ship.**

RepoLens is an open-source CLI that runs structured code reviews against projects you care about: on your machine, or cloned from GitHub, Bitbucket, Hugging Face, or any Git URL. It follows a clear **P1 → P2 → P3** pass (security → bugs/reliability/performance → architecture/quality) and writes audit-friendly reports with impact, remediation steps, and code-example fixes for Critical/High findings.

> **Status:** Alpha `0.1.0a1` — **Phases 0–6 complete**; **6.x** (enterprise scanner depth / CI triage) next  
> Local CLI · remotes · optional scanners · explain + diagrams · GitHub Action · opt-in local learning · PyPI Trusted Publishing workflow  
> Install: `pip install -e .` from a clone, or `pip install "repolens @ git+https://github.com/vksvicky/RepoLens.git"`  
> Docs: [phases](./docs/phases.md) · [FAQ](./docs/faq.md) · [rules](./docs/rules.md) · [install extras](./docs/install-extras.md) · [CI / Action](./docs/ci.md) · [remotes](./docs/remote-sources.md) · [scanners](./docs/scanners.md) · [local learning](./docs/local-learning.md) · [publishing](./docs/publishing.md)

---

## Why RepoLens?

| Need | How RepoLens helps |
|------|--------------------|
| Review **any** project, not one vendor’s stack | Local paths + Git remotes |
| Security without ignoring architecture | Full review + `sentinel` security-only mode |
| Actionable findings | Impact, fix plan, **code examples** on Critical/High |
| Shareable audits | Markdown reports (PDF via pandoc / Print) |
| Production honesty | Complements—does not replace—CI, tests, and scanners |

RepoLens is **not** a replacement for Semgrep, CodeQL, Dependabot, Snyk, or your test suite. Those stay in CI. RepoLens adds a consistent, human-readable due-diligence layer you can run anywhere.

---

## Modes

| Command | What it does |
|---------|--------------|
| `repolens review` | Full dual review: P1 security + P2 reliability + P3 architecture |
| `repolens sentinel` | **Security-only** scan (P1 playbook) |
| `repolens architecture` | Architecture / production-readiness audit |
| `repolens plugins` | Optional scanners: `status` / `list` / `install` |
| `repolens learn` | Opt-in local index: `build` / `status` / `clear` |
| `repolens init` | Write user config (cloud key, Ollama, or none) |
| `repolens explain` | Deep-dive one finding by ID (solutions + diagram) |
| `repolens export` | Export / convert a report (e.g. Markdown → PDF via pandoc) |
| `repolens version` | Print package version |

**What gets checked?** See **[docs/rules.md](./docs/rules.md)** — plain guide to rules, why they exist, and how to turn them on/off.

---

## Languages & tools

- **CLI:** Python 3.11+  
- **Reviews:** language-agnostic, with first-class focus on JS/TS, Python, Go, JVM, C#, Ruby, PHP, Rust, Swift (+ IaC/config)  
- **AI:** Bring your own cloud key **or** run a local model (e.g. Ollama)—no embedded RepoLens key  
- **CVE / SAST / secrets:** optional plugins (OSV, Semgrep, gitleaks)—not in the slim default install  
- **Local learning:** opt-in on-disk FTS index (`repolens learn`), informed consent first  
- **CI:** official GitHub Action (`action.yml`) — see [docs/ci.md](./docs/ci.md)

Full answers: **[docs/faq.md](./docs/faq.md)** · **[docs/design/ai-keys-scanners-and-local-learning.md](./docs/design/ai-keys-scanners-and-local-learning.md)**.  
**Setup (cloud / Ollama / scanners):** **[docs/setup-ai-and-scanners.md](./docs/setup-ai-and-scanners.md)**.  
**Try it (local + GitHub / Bitbucket / HF / git URL):** **[docs/try-on-your-repo.md](./docs/try-on-your-repo.md)**.  
Interactive helper: `./scripts/repolens-guided.sh` (see [try-on-your-repo](docs/try-on-your-repo.md#guided-review-interactive)).

---

## Quick start

### Install extras (`[dev]`, `[scanners]`, …)

These are **optional parts of the RepoLens package** (defined in this repo’s [`pyproject.toml`](./pyproject.toml)). They are **not** settings inside the apps you review.

| Extra | Command | What you get |
|-------|---------|--------------|
| *(none)* | `pip install -e .` | CLI only |
| **dev** | `pip install -e ".[dev]"` | + pytest, pytest-cov, ruff, mypy |
| **scanners** | `pip install -e ".[scanners]"` | + Semgrep (gitleaks/osv still via `repolens plugins install`) |
| **local-ml** | `pip install -e ".[local-ml]"` | + sentence-transformers |

Full detail: **[docs/install-extras.md](./docs/install-extras.md)**.

```bash
# From a clone
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# First-run: cloud key, local Ollama, or none
# Ollama: uses a model from `ollama list` (or pass --model NAME)
repolens init --provider ollama   # or openai | anthropic | deepseek | none

# Inventory + report skeleton (no model call)
repolens review --path ./my-app --dry-run

# Optional scanners (secrets / SAST / CVE)
repolens plugins install all
repolens review --path ./my-app --scanners-only

# Opt-in local learning (stays on disk)
repolens learn build --path ./my-app --accept-local-learning

# Full local review (requires configured provider + key/Ollama)
# Progress lines + LLM heartbeats by default; add -v for more detail
# Deep coverage (multi-pass + heuristics) is on by default; use --no-deep for single-shot
repolens review --path ./my-app --verbose
# After first run: warm packs + recommended timeout
repolens adaptive status --path ./my-app
repolens sentinel --path ./my-app
```

### Sources (local + remotes)

```bash
# Local folder
repolens review --path ./my-app --dry-run

# GitHub / Bitbucket / Hugging Face / any git URL
repolens review --github owner/repo --ref main --dry-run
repolens review --bitbucket workspace/repo --ref main --dry-run
repolens review --hf org/model --dry-run
repolens review --hf datasets/org/dataset-name --dry-run
repolens review --git-url https://github.com/owner/repo.git --ref main --dry-run
```

Private remotes: `GITHUB_TOKEN` / `BITBUCKET_TOKEN` / `HF_TOKEN` (or `gh auth login`).  
Full examples: [docs/try-on-your-repo.md](./docs/try-on-your-repo.md) · [docs/remote-sources.md](./docs/remote-sources.md) · [docs/scanners.md](./docs/scanners.md).

### GitHub Actions

```yaml
- uses: actions/checkout@v4
- uses: vksvicky/RepoLens@main
  with:
    path: .
    run: auto          # scanners always; LLM if API key secret is set
    # or: run: dry-run
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}  # optional
```

Details: [docs/ci.md](./docs/ci.md).

Playbooks also work with any LLM chat: [docs/using-playbooks.md](./docs/using-playbooks.md).

---

## Reports

### In the terminal
Summaries show **confidence %**, severity counts, and top findings.

### Saved Markdown (default artifact)
```text
reports/gate_review_report_{mode}_YYYY-MM-DD_HHMM.md
```
`mode` is `review`, `sentinel`, or `architecture`. Each Critical/High finding includes explanation, **impact**, recommended fix, and a **code example**. Reports include an **Automated scanners** section when scanners run.

### PDF
```bash
pandoc reports/gate_review_report_review_YYYY-MM-DD_HHMM.md -o reports/gate_review_report_review_YYYY-MM-DD_HHMM.pdf
# or: Print → Save as PDF from a Markdown preview
```

---

## Playbooks & rules

| Playbook | File |
|----------|------|
| Security (P1 / `sentinel`) | [playbooks/security.md](./playbooks/security.md) |
| Architecture (release / full audit) | [playbooks/architecture.md](./playbooks/architecture.md) |

**Rules** (what is checked, why, enable/disable): **[docs/rules.md](./docs/rules.md)**.  
Playbook files: [playbooks/README.md](./playbooks/README.md). Contributions: [docs/CONTRIBUTING.md](./docs/CONTRIBUTING.md).

---

## Repository layout

```text
RepoLens/
├── README.md                 # This page
├── LICENSE                   # MIT
├── action.yml                # GitHub Action (composite)
├── pyproject.toml            # Python package
├── src/repolens/             # CLI, pipeline, scanners, learning
├── tests/                    # pytest suite
├── playbooks/                # Review instruction sources
├── examples/monorepo/        # Sample project config
├── docs/                     # Guides, FAQ, ADR, design, phases
└── .github/workflows/        # CI, publish, Action example
```

Naming conventions: [docs/README.md](./docs/README.md#naming-pattern).

---

## Roadmap

| Phase | Scope | Status |
|-------|--------|--------|
| **0** | Docs, playbooks, design | Done |
| **1** | Core CLI (local path, reports, BYOK / Ollama) | Done (alpha) |
| **2** | Remotes (`--git-url`, `--github`, `--bitbucket`, `--hf`) | Done |
| **3** | Optional scanners (gitleaks, Semgrep, OSV) | Done |
| **4** | GitHub Action, PyPI publish path, local learning | Done |
| **Next** | Harden publish / marketplace polish / richer embeddings | Open |

Tracker: **[docs/phases.md](./docs/phases.md)** · Design: **[docs/design/](./docs/design/)** · ADR: **[docs/adr/01_analysis_runtime_architecture.md](./docs/adr/01_analysis_runtime_architecture.md)**.

---

## Contributing

- [docs/CONTRIBUTING.md](./docs/CONTRIBUTING.md)
- [docs/CODE_OF_CONDUCT.md](./docs/CODE_OF_CONDUCT.md)
- [docs/SECURITY.md](./docs/SECURITY.md) for vulnerability reports
- [docs/SUPPORT.md](./docs/SUPPORT.md)

---

## Disclaimer (AI / LLM output)

RepoLens findings and suggestions may be produced or assisted by AI/LLMs, heuristics, and optional scanners. They can be wrong or incomplete. **You** are responsible for verifying results before you act. Authors accept **no liability** for harm from reliance on AI/LLM or tool-assisted output. Reports are not a certification or professional audit engagement. Full text appears in every Markdown report under **Disclaimer**, and in the [FAQ](./docs/faq.md#disclaimer-ai--llm-output).

---

## License

[MIT](./LICENSE) — use it, fork it, adapt the playbooks for your org. Software is provided **as is** (see the licence).
