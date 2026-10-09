# Why We Built RepoLens: Zero-Infra Code Audits, Tech Debt, and the Hard Truth About Local LLMs

*By a developer, consultant, and trainer at [CycleRunCode Club](https://cycleruncode.club) who got tired of bad options.*

---

## The Tuesday Morning Problem

If you've ever worked as a fractional CTO, an engineering consultant, or an M&A tech auditor, you know the scenario:

It’s Tuesday morning. You’re handed access to a 500-file repository you’ve never seen before. Leadership wants a defensible audit by Thursday:
- *Are there critical security holes or leaked credentials?*
- *Is the architecture clean, or is it a tangled ball of circular imports?*
- *Can this team actually scale this, or is it held together with duct tape and hope?*

Here are your traditional options:

1. **Option A: Stand up SonarQube.**  
   Now you’re dealing with a Java runtime, provisioning a PostgreSQL database, configuring authentication, and begging IT for infrastructure. You don’t have time to manage a server; you need an answer.

2. **Option B: Connect a SaaS PR bot (CodeRabbit, Bito, etc.).**  
   Except the client has strict NDAs, or the repo is proprietary IP. You can’t just hook up third-party webhooks and spray their source code across someone else’s cloud without a two-month legal review.

3. **Option C: Bash script gluing linters together.**  
   `semgrep && trivy && gitleaks`. You end up with three separate JSON dumps, duplicated CVEs, zero cross-tool prioritization, no import graph analysis, and no cohesive narrative you could show an engineering director.

4. **Option D: Paste files into ChatGPT / Claude.**  
   It hits context limits immediately, misses multi-file dependencies, hallucinates file paths that don't exist, and gives you generic advice like *"consider adding docstrings"*.

We built **RepoLens** because none of those options solved the actual job. It's part of our wider toolkit at [CycleRunCode Club](https://cycleruncode.club), where we teach playbooks for structured code reviews, architectural boundaries, and shipping with confidence.

---

## What RepoLens Actually Is

RepoLens is an open-source CLI (`pip install repolens-audit`) designed for **due-diligence audits and release gates without infrastructure**. 

It runs on your machine or on an ephemeral CI runner. No database, no vendor cloud, no telemetry lock-in.

It divides the review into two distinct lanes:

### 1. Fast Brain (0.5 seconds, 100% Deterministic)
Before touching an AI model, Fast Brain runs deterministic analysis on your local tree:
- **Scanners:** Integrates Gitleaks, Semgrep, OSV, Trivy, and Checkov.
- **Structural Heuristics:** Flags mega-files, deep nesting, near-clones, TODO density, and `.gitignore` hygiene.
- **Import Graph & Cyclicity Ratchet:** Parses module dependencies (`grimp` for Python, `tree-sitter` for JS/TS/Go/Rust/C#) to calculate circular dependency groups and verify strict layer boundaries (`repolens.yaml`).

If all you need is a fast pre-commit check or a PR gate in GitHub Actions, Fast Brain finishes in under 2 seconds and costs \$0.

### 2. Slow Brain (Multi-Role Synthesis)
When you need deep due diligence, Slow Brain runs a structured multi-pass review:
- **P1 (Security):** Sinks, auth, secrets, transport, injection.
- **P2 (Reliability & Performance):** Concurrency, transactions, error recovery, edge cases.
- **P3 (Architecture):** Modularity, SOLID boundaries, cyclicity refactoring.

Crucially, you **bring your own compute**: either private enterprise cloud keys (Bedrock, Vertex, Gemini, Anthropic) or completely offline local models via Ollama. Source code never leaves the boundary you define.

---

## The Reality Check: What Broke and What We Learned

Building an AI-assisted CLI sounds great on paper until you run it against a real 500-file repository. Here’s what happened on one of our recent dogfood runs with a local 32B model, and why you have to design defensively.

### The "Gate 0%" Trap
We ran a deep audit on a repository: 493 files, 0 Critical bugs, 0 High bugs, all 4 scanners clean, 100% security confidence, and 95% reliability confidence.

The final verdict on the report?  
**`Gate confidence: 0%`**

Why? Because the local LLM generated valid JSON with 5 findings and 27 checklist answers, but marked 3 complexity findings as `HIGH` with `"codeExample": null`. 

Our Pydantic schema validator rejected `null` on High findings $\to$ the repair pass failed $\to$ P3 was marked `degraded` $\to$ our coverage engine wiped out all 27 architectural checklist answers $\to$ the minimum band score collapsed to 0%.

### The Engineering Lesson
**Never conflate a tool packaging/schema error with product defect quality.**

If an LLM pass glitches on JSON formatting, the code isn't at 0% confidence—the *packaging of that pass was incomplete*. 

We immediately hardened the pipeline:
1. **Defensive Coercion:** If a model omits a code example or impact string, inject a fallback placeholder (`// Model omitted codeExample — verify manually`) instead of crashing Pydantic. Keep the High severity, but don't drop the pass.
2. **Gate Insulation:** Degraded passes are marked `INCOMPLETE / UNVERIFIED`, not scored as a 0% floor that drags down passing security and reliability bands.
3. **Productizing Two Speeds:** Never make 1-hour LLM runs the default PR gate. Use `--preset pr` (deterministic, sub-second, zero LLM) for CI, and save `--preset release` for scheduled release audits.

---

## Where RepoLens Fits in the Market

If you're evaluating tools today, here is the honest division of labor:

- **Need continuous quality profiles across 50 enterprise teams?**  
  *Use SonarQube.* It has the server infrastructure, dashboards, and enterprise governance built out.
- **Want real-time conversational comments on every PR diff?**  
  *Use CodeRabbit or GitHub Copilot PR Review.* They are purpose-built for inline PR velocity.
- **Need a zero-infra security & architecture audit on an unfamiliar repo — scanners in seconds, deep narrative in tens of minutes via BYOK (or hours on local 32B Ollama)?**  
  *That’s RepoLens.* 

It gives you the due-diligence report, cyclicity graph, and scanner evidence in a portable Markdown/PDF bundle with zero platform to maintain.

---

## How to Try It

```bash
# 1. Install via pipx (no server required)
pipx install "repolens-audit[scanners]"

# 2. Run the deterministic fast gate on your repo (< 2 seconds)
repolens review --path . --scanners-only --fail-on HIGH

# 3. Check for circular dependencies & layer breaches
repolens check --diff

# 4. Preview full deep packs without spending tokens
repolens plan
```

- **Open Source Repository:** [github.com/vksvicky/RepoLens](https://github.com/vksvicky/RepoLens)
- **Playbooks, Training & Due-Diligence Frameworks:** [CycleRunCode Club](https://cycleruncode.club)

Run it locally, inspect the generated report, and keep your code where it belongs: on your machine.
