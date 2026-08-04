# FAQ

## Decisions in plain English (start here)

If you only read one section, read this.

| Question | Plain answer |
|----------|--------------|
| **Do I need an AI key?** | For cloud AI (ChatGPT-style providers), **yes—you use your own key**. You can also run AI **on your own computer** (no cloud key). Scanners-only (`--scanners-only`) needs no AI key. |
| **Is it self-sufficient?** | The download is the **review process and templates**, not a free built-in AI brain. For a full written review you add **your cloud key** or a **local AI**. For maximum privacy, use local AI. |
| **Extra security software?** | Kept **optional** so the default install stays small. Use tools on your `PATH`, or `repolens plugins install` / `repolens[scanners]`—no forced huge downloads. |
| **OWASP / CVE?** | **AI** explains security themes (OWASP-style) in *your* code with fix suggestions. **OSV / Semgrep / gitleaks** list deterministic evidence (**CVE** IDs, secrets, SAST). AI alone is not a complete CVE list. |
| **Does it learn from my repo?** | **Yes (opt-in):** on your machine only, off by default, and we tell you before it starts (`repolens learn`). We don’t upload your project to train a central RepoLens model. If you use cloud AI, that provider may still see code excerpts you send for the review. |
| **What is `.[dev]` / `.[scanners]`?** | Optional **pip extras when installing RepoLens** (listed in RepoLens’s `pyproject.toml`). They are **not** part of the project you review. See [install-extras.md](./install-extras.md). |
| **I have Ollama — why does review fail?** | RepoLens needs a one-time `repolens init --provider ollama` (writes `~/.config/repolens/config.toml`). `init` uses a model from `ollama list` when `--model` is omitted. See [setup-ai-and-scanners.md](./setup-ai-and-scanners.md#option-b--local-ai-on-your-computer-eg-ollama). |

Longer narrative: [design/ai-keys-scanners-and-local-learning.md §5](./design/ai-keys-scanners-and-local-learning.md#5-decision-summary-plain-language).  

**Setup steps for all three options:** [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) (cloud key · local Ollama · scanners only).

---

## What is the adaptive cache (Phase 5)?

On each review RepoLens can maintain `.repolens/repolens.sqlite` (local): file fingerprints + run timings + optional FTS content (opt-in). Later runs prefer **changed + P1** files (`adaptive.mode=auto`), and store a **recommended timeout** per project. Override with `--timeout`, config, or `--full` for a full pack. Inspect with `repolens adaptive status --path .`. Disable with `[adaptive] enabled = false`.

---

## What is deep coverage?

**Deep mode** (default **on** for LLM runs) runs heuristics, then chunked P1→P3 passes with a **rules registry** checklist (coverage IDs), and merges/dedupes into one report. Use `--no-deep` for a single-shot LLM call (faster, thinner on large repos).

| Flag / config | Effect |
|---------------|--------|
| *(default)* / `--deep` | Multi-pass deep coverage + heuristics + coverage tally |
| `--no-deep` | Single-shot LLM (legacy thin path) |
| `--full-audit` | Deep **and** full architecture checklist + scores |
| `[deep]` in config | `enabled`, `chars_per_pass`, `mega_file_lines` |

**Rules** load by **id** from a registry (project `.repolens/rules/` → user config → packaged defaults)—not hard-coded Markdown paths on the author’s machine. Override a rule with `.repolens/rules/<id>.md`.

If the model returns invalid JSON, RepoLens still writes a report (scanners + heuristics + any salvageable issues) and exits **0**.

**Cloud tip (Phase A):** Anthropic / OpenAI use the **same `--deep` pipeline**—pick the provider via `repolens init`; deep mode is what drives checklist completeness on large repos (e.g. PatternSorcerer-sized trees).

Guided wizard: `./scripts/repolens-guided.sh` prompts for deep (default **Y** on review / full-audit).

---

## Why did I get `LLM … timed out`?

The HTTP wait for one model call expired (old default was **120s**; Ollama now defaults to **900s**). Local 7B models on large prompts often need longer.

```bash
repolens init --provider ollama --force   # refreshes config incl. timeout_seconds=900
repolens review --path "$TARGET" --out "$TARGET/reports" --timeout 1800 --verbose
# or narrow: --mode diff --since HEAD~20
# or skip LLM: --scanners-only
```

Also set `timeout_seconds` in `~/.config/repolens/config.toml` or `export REPOLENS_TIMEOUT=1800`.

---

## Why does `repolens review` look stuck? How do I see progress?

Full LLM reviews (especially local Ollama) can take minutes with little network activity. By default RepoLens prints phase lines (`Inventory` → `Scanners` → `LLM` → `Writing report`) and a heartbeat every **15s** while waiting on the model.

| Flag | Effect |
|------|--------|
| *(default)* | Phase lines + LLM spinner (TTY) + heartbeat |
| `--verbose` / `-v` | Extra detail (file sample, per-scanner status, prompt size) |
| `--heartbeat 30` | Change heartbeat interval (seconds) |
| `--heartbeat 0` | Disable heartbeats (phases still print) |
| `--quiet` / `-q` | Hide progress (summary/report paths still print) |

---

## I already use Ollama — why do I still need `repolens init`?

RepoLens does **not** auto-select a provider. `repolens init --provider ollama` writes your user config and sets `model` from **`ollama list`** (first installed model) unless you pass `--model`.

```bash
ollama list
repolens init --provider ollama --force
# or: repolens init --provider ollama --model qwen2.5:7b --force
```

A 404 from the provider usually means the config model name is not installed — fix with `--model` matching `ollama list`, or `ollama pull …`.

Full steps: [setup-ai-and-scanners.md](./setup-ai-and-scanners.md#option-b--local-ai-on-your-computer-eg-ollama) · walkthrough: [try-on-your-repo.md](./try-on-your-repo.md).

---

## What are `[dev]` and `[scanners]`? Where do they live?

They are **install options for the RepoLens tool**, not configuration for each repository you analyse.

- **Defined in:** [`pyproject.toml`](../pyproject.toml) → `[project.optional-dependencies]` in the **RepoLens** repo  
- **Used when:** you run `pip install -e ".[dev]"` (or `repolens[scanners]` from PyPI/git)  
- **Not required in:** `acme-api` or any other target of `repolens review --path …`

| Extra | Packages | Notes |
|-------|----------|-------|
| `dev` | pytest, pytest-cov, ruff, mypy | For developing / dogfooding RepoLens |
| `scanners` | semgrep only | gitleaks + osv come from `repolens plugins install` |
| `local-ml` | sentence-transformers | Opt-in local learning |

Full table and examples: [install-extras.md](./install-extras.md).

---

## Do I need an AI API key? Is RepoLens self-sufficient?

**Short answer:** For the full dual review (natural-language findings + code-example fixes), RepoLens needs **a model**. That can be a **cloud API key you bring** or a **local model** (e.g. Ollama). It does **not** ship with a built-in hosted AI key.

| Setup | AI key? | Works offline? | What you get |
|-------|---------|----------------|--------------|
| Cloud LLM (OpenAI, Anthropic, DeepSeek, …) | **Yes** — your key in env/config | No (calls provider) | Full `review` / `sentinel` / `architecture` |
| Local LLM (Ollama or compatible) | **No** cloud key | Yes (after model download) | Same modes, data stays on your machine except what you choose to send nowhere |
| Scanners only (Phase 3) | No | Mostly yes* | Secrets / SAST / CVE lists — **not** full architecture narrative |
| Playbooks in an LLM chat today | Uses that product’s AI | Per that product | Same playbooks, no RepoLens CLI yet |

\*CVE DBs may need periodic updates.

**Self-sufficient?**  
- **Slim default CLI:** not by itself — BYOK or local model.  
- **Privacy-sensitive / air-gapped:** use **local LLM + optional local scanners**.  
- RepoLens never embeds a shared vendor API key.

Keys stay in environment variables or your config secret references — **never** in git or report files. Details: [design/ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md).

**Concrete setup steps:** [setup-ai-and-scanners.md](./setup-ai-and-scanners.md).

---

## What languages does RepoLens support?

Two different questions—answered separately.

### 1) Languages of **projects you review** (targets)

RepoLens is **source-agnostic**: if it is text in a git tree, the LLM playbooks can review it. Quality and heuristics are **tiered**:

| Tier | Languages / ecosystems | What you get |
|------|------------------------|--------------|
| **First-class (Phase 1–2 focus)** | **JavaScript / TypeScript**, **Python**, **Go**, **Java / Kotlin**, **C#**, **Ruby**, **PHP**, **Rust**, **Swift** | Strong playbook examples, common framework patterns (React/Next, Django/Flask/FastAPI, Spring, Rails, Laravel, etc.), clearer code-example fixes |
| **Supported well** | **Shell**, **Terraform / OpenTofu**, **Kubernetes YAML**, **SQL**, **Dart/Flutter**, **C / C++** | Solid security & config review; architecture depth varies by project shape |
| **Best-effort** | Any other text language (Scala, Elixir, Haskell, R, MATLAB, …) | Generic secure-coding + architecture questions; fewer idiomatic examples |
| **Out of band** | Pure binaries, minified bundles, huge generated assets | Skipped or size-capped; not treated as primary review surface |

**Infrastructure-as-code and config** count as first-class security surface: `.env*` (never commit secrets), Dockerfiles, CI YAML, cloud templates, `package.json` / `pyproject.toml` / `go.mod`, etc.

Hugging Face repos (models/datasets/Spaces) are reviewed as **git content** (code, configs, cards)—not as model weights inside the CLI.

### 2) Language the **RepoLens CLI** is written in

**Python 3.11+** (decision locked in Phase 0). Install target: `pipx` / `uv` / PyPI as `repolens`. Details: [design/cli-and-report-schema.md](./design/cli-and-report-schema.md).

---

## When scanning, what extra libraries are required? Can you build them in?

### Always required (Phase 1)

| Piece | Bundled with `pip install repolens`? |
|-------|--------------------------------------|
| Python package deps (`typer`, `httpx`, …) | **Yes** |
| Playbooks | **Yes** |
| **Git** on PATH | **No** — use your system Git |
| LLM provider (cloud key or local Ollama) | **No** — you supply |

### Optional security scanners (Phase 3 — shipped)

| Tool | Purpose | Default install? |
|------|---------|------------------|
| gitleaks | Secrets | **Optional** — PATH or `repolens plugins install` |
| Semgrep | SAST / pattern rules | **Optional** — PATH, cache venv, or `.[scanners]` |
| OSV-Scanner | **CVE** / dependency vulns | **Optional** — PATH or plugins install |
| pandoc | PDF export | **Optional** |

**Can we build them in?**  
Use `repolens plugins install …` (consent download) or `pip install "repolens[scanners]"` for Semgrep via pip — large native scanners stay out of the slim default wheel. Missing scanners never break the LLM review path unless you pass `--require-scanners`.

Guide: [scanners.md](./scanners.md) · Design: [ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md).

---

## How do OWASP / CVE / security audits work?

RepoLens uses **layers** — different tools for different jobs:

| Layer | Question it answers | How |
|-------|---------------------|-----|
| **LLM + `sentinel` / security playbook** | “What OWASP-*style* issues appear in *this* code, with fixes?” | Heuristic review; tags CWE/OWASP categories when possible |
| **Secret scanner** | “Are live credentials in the tree?” | gitleaks (`--scanners` / plugins) |
| **SAST** | “Do known bad patterns match?” | Semgrep (`--scanners` / plugins) |
| **CVE / SCA** | “Are dependencies known-vulnerable?” | OSV-Scanner (`--scanners` / plugins) |
| **Your CI** | “Is this enforced on every PR?” | Dependabot, CodeQL, Snyk, etc. — we *call out gaps*, we don’t replace them |

**Important:** The LLM layer is **not** a CVE database. For audit-grade **CVE** lists, enable the dependency scanner plugin (or your existing SCA in CI). “OWASP compliant” is not a certification we stamp; we **align findings** to OWASP Top 10 / CWE and recommend deterministic scanners for evidence packs.

---

## Can RepoLens learn from my repo with ML? Is that local?

**Yes (Phase 4 — shipped), local-first and opt-in.** See [local-learning.md](./local-learning.md).

| Behaviour | Detail |
|-----------|--------|
| What | Optional local index/embeddings + preference memory (dismissed false positives, ignore paths) to improve later reviews |
| Where | On **your disk** (e.g. `.repolens/` or user cache) |
| Upload to RepoLens? | **No** — the CLI has no RepoLens training cloud |
| Notice | First enablement shows an explicit consent message |
| Default | **Off** until you accept |
| Cloud LLM caveat | If you still use a **cloud** API key, **excerpts may go to that provider**; local learning does not remove that. Use Ollama for fully local prompts |

Disable by config or deleting `.repolens/`. Full policy: [design/ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md).

---

## Is it safe to review untrusted repositories?

RepoLens reads source from `--path` and may send excerpts to your configured LLM. Project `.repolens.toml` **cannot** override `provider`, `base_url`, or `api_key_env` unless you pass `--trust-project-config`. Put provider settings in `~/.config/repolens/config.toml` or `REPOLENS_*` env vars. Symlinks and report paths that escape the project root are skipped/rejected.

## What tools and libraries does RepoLens integrate with?

### Required to run full reviews (Phase 1)

| Tool | Role |
|------|------|
| **Git** | Local repos, remotes, diff/`--since` |
| **An LLM provider** | Cloud BYOK **or** local (Ollama) |
| **Python 3.11+** | Runtime for the CLI |

### Optional durability plugins (Phase 3 — shipped)

| Tool | Role |
|------|------|
| **gitleaks** | Secret scanning |
| **Semgrep** | SAST / rule-based findings |
| **OSV-Scanner** | Dependency CVEs |
| **pandoc** | Markdown → PDF export |

See [scanners.md](./scanners.md).

### Explicitly *not* replaced

RepoLens complements—does **not** replace—**pytest/jest/etc.**, **CI**, **Dependabot/Renovate**, **CodeQL**, **Snyk**, or your hosting provider’s secret scanning.

### Hosting sources (Phase 2)

Details: [remote-sources.md](./remote-sources.md).

| Source | Support |
|--------|---------|
| Local path (`--path`) | Done (Phase 1) |
| Generic git URL (`--git-url`) | Done (Phase 2 MVP) |
| GitHub (`--github`) | Done (Phase 2 MVP) |
| Bitbucket (`--bitbucket`) | Done (Phase 2) |
| Hugging Face Hub (`--hf`) | Done (Phase 2) |

---

## Do I need the CLI to use RepoLens today?

No. Use the [playbooks](../playbooks/) with any LLM that can read your repo—see [using-playbooks.md](./using-playbooks.md).

---

## What is `repolens sentinel`?

Security-only mode (P1 playbook). Faster guardrail pass without a full architecture audit. Full dual review is `repolens review`.

---

## Will RepoLens auto-push my code?

No. It produces reports and exit codes. Git push stays under your control.

---

## How do I export a PDF?

Prefer Markdown reports, then:

```bash
pandoc reports/gate_review_report_YYYY-MM-DD.md -o report.pdf
```

or Print → Save as PDF from a Markdown preview.

---

## Is LLM-only review enough for production?

No. Use RepoLens as a due-diligence layer **plus** tests, CI, and mature scanners (CVE/SAST/secrets). See [phases.md](./phases.md) Phase 3 and the design note above.

## Can we use this in corporate CI/CD (Jenkins, email, dashboards)?

**Local + GitHub Actions / Bitbucket artifacts:** documented and usable now ([ci.md](./ci.md)).

**Jenkins, CircleCI, email, internal dashboards:** planned as **Phase 6** — design sketch in [design/phase-6-enterprise-ci-and-report-delivery.md](./design/phase-6-enterprise-ci-and-report-delivery.md). Pattern: run on the CI agent → archive `reports/**` → notify or ingest JSON into *your* tools. RepoLens does not ship a hosted dashboard.

---

---

## How does RepoLens analyse a repository?

See **[ADR-01: Analysis runtime architecture](./adr/01_analysis_runtime_architecture.md)** for pipeline diagrams. Colour legend: [adr/_diagram_legend.md](./adr/_diagram_legend.md).

---

## Where is the roadmap?

[phases.md](./phases.md).
