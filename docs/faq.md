# FAQ

## Decisions in plain English (start here)

If you only read one section, read this.

| Question | Plain answer |
|----------|--------------|
| **Do I need an AI key?** | For cloud AI (ChatGPT-style providers), **yes—you use your own key**. You can also run AI **on your own computer** (no cloud key). Checklist-only scans (later) need no AI key. |
| **Is it self-sufficient?** | The download is the **review process and templates**, not a free built-in AI brain. For a full written review you add **your cloud key** or a **local AI**. For maximum privacy, use local AI. |
| **Extra security software?** | Kept **optional** so the default install stays small. RepoLens can use tools you already have, or help install them later if you ask—it won’t force huge downloads on everyone. |
| **OWASP / CVE?** | **AI** explains security themes (OWASP-style) in *your* code with fix suggestions. **Separate tools** list known library holes (**CVE** IDs). We use both kinds of check; AI alone is not a complete CVE list. |
| **Does it learn from my repo?** | **Planned:** yes, but **on your machine only**, **off by default**, and **we tell you** before it starts. We don’t upload your project to train a central RepoLens model. If you use cloud AI, that provider may still see code excerpts you send for the review. |

Longer narrative: [design/ai-keys-scanners-and-local-learning.md §5](./design/ai-keys-scanners-and-local-learning.md#5-decision-summary-plain-language).  

**Setup steps for all three options:** [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) (cloud key · local Ollama · scanners only).

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

### Optional security scanners (Phase 3)

| Tool | Purpose | Default install? |
|------|---------|------------------|
| gitleaks (or similar) | Secrets | **Optional** — detect if installed |
| Semgrep | SAST / many OWASP-oriented rules | **Optional** |
| OSV-Scanner / Grype | **CVE** / dependency vulns | **Optional** |
| pandoc | PDF export | **Optional** |

**Can we build them in?**  
We can ship **optional extras** or `repolens plugins install …` that fetch pinned binaries — but we will **not** put large native scanners into the **default** slim package. Missing scanners never break the LLM review path unless you pass `--require-scanners`.

Design: [ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md).

---

## How do OWASP / CVE / security audits work?

RepoLens uses **layers** — different tools for different jobs:

| Layer | Question it answers | How |
|-------|---------------------|-----|
| **LLM + `sentinel` / security playbook** | “What OWASP-*style* issues appear in *this* code, with fixes?” | Heuristic review; tags CWE/OWASP categories when possible |
| **Secret scanner** | “Are live credentials in the tree?” | gitleaks (Phase 3) |
| **SAST** | “Do known bad patterns match?” | Semgrep + rulesets (Phase 3) |
| **CVE / SCA** | “Are dependencies known-vulnerable?” | OSV-Scanner / similar (Phase 3) |
| **Your CI** | “Is this enforced on every PR?” | Dependabot, CodeQL, Snyk, etc. — we *call out gaps*, we don’t replace them |

**Important:** The LLM layer is **not** a CVE database. For audit-grade **CVE** lists, enable the dependency scanner plugin (or your existing SCA in CI). “OWASP compliant” is not a certification we stamp; we **align findings** to OWASP Top 10 / CWE and recommend deterministic scanners for evidence packs.

---

## Can RepoLens learn from my repo with ML? Is that local?

**Yes (planned Phase 4+), local-first and opt-in.**

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

### Optional durability plugins (Phase 3)

| Tool | Role |
|------|------|
| **gitleaks** (or equivalent) | Secret scanning |
| **Semgrep** | SAST / rule-based findings |
| **OSV-Scanner** / similar | Dependency CVEs |
| **pandoc** | Markdown → PDF export |

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

---

## How does RepoLens analyse a repository?

See **[ADR-01: Analysis runtime architecture](./adr/01_analysis_runtime_architecture.md)** for pipeline diagrams. Colour legend: [adr/_diagram_legend.md](./adr/_diagram_legend.md).

---

## Where is the roadmap?

[phases.md](./phases.md).
