# Reddit Post: Introducing RepoLens

**Suggested Subreddits:** `r/programming`, `r/devops`, `r/python`, `r/softwareengineering`  
**Title:** *I got tired of standing up Sonar servers and uploading client IP to SaaS review bots, so I built an open-source zero-infra audit CLI (RepoLens)*

---

### Post Content (Markdown formatted for Reddit)

Hey r/programming,

Over the past few years doing engineering consulting and tech due diligence, I kept hitting the same wall whenever I was handed an unfamiliar codebase:

- **SonarQube** wants a JVM, a Postgres DB, and an IT ticket.
- **SaaS PR bots** want webhook access and your source code on their servers (a non-starter when working under client NDAs).
- **Bash scripts** (`semgrep && trivy && gitleaks`) dump 3 raw JSON blobs with duplicated CVEs, zero cross-file context, and no architecture insights.
- **Pasting files into an LLM chat** hallucinates dependencies and misses circular imports entirely.

To solve this, we've been building **RepoLens** (open-source, Apache 2.0) alongside our engineering playbooks at [CycleRunCode Club](https://cycleruncode.club).

### What it actually does

It's a CLI (`pipx install repolens-audit`) that unifies deterministic scanners and multi-pass AI reviews with zero infrastructure:

1. **Fast Brain (Sub-second, 0 LLM):**
   - Runs deterministic scanners (Gitleaks, Semgrep, OSV, Trivy, Checkov).
   - Builds import graphs (`grimp` for Python, `tree-sitter` for JS/TS/Go/Rust/C#) to detect circular dependencies and enforce strict architectural layer boundaries (`repolens.yaml`).
   - Flags structural smells (mega-files, deep nesting, TODO density, near-clones).
   - Fast enough for pre-commit or standard PR gates (`repolens review --scanners-only --fail-on HIGH`).

2. **Slow Brain (Multi-Role Synthesis):**
   - Follows an explicit multi-pass playbook: P1 (Security) → P2 (Reliability/Perf) → P3 (Architecture).
   - Outputs Markdown, PDF, and SARIF reports with concrete code fix examples for High/Critical issues.
   - **Local & Private:** Runs 100% offline via local Ollama models (e.g. Qwen 2.5 Coder 32B, DeepSeek) or private cloud BYOK (Bedrock / Vertex / Gemini). No vendor SaaS.

### What broke during testing (The "Gate 0%" Trap)

I wanted to share an honest post-mortem from a dogfood run against a ~500-file repository.

We ran a 70-minute deep audit using a local 32B model. All 4 scanners passed clean, 0 Critical, 0 High bugs, 100% security coverage, 95% reliability. 

The final report verdict? **Gate confidence: 0%**.

Why? The local LLM generated valid JSON, but marked 3 complexity findings as `HIGH` with `"codeExample": null`. Our strict Pydantic model insisted that Critical/High findings must have a non-empty codeExample. Pydantic raised a `ValidationError` → micro-repair failed → P3 degraded → our coverage engine marked all 27 architectural checklist items as "unanswered" → the minimum band score collapsed to 0%.

The takeaway: **Never let AI packaging glitches masquerade as code security failures.**

We rewrote the ingestion spine:
- Blank fields auto-inject placeholder comments instead of crashing validation.
- Degraded LLM passes are reported as `INCOMPLETE / UNVERIFIED`, not a 0% code defect score.
- We split the CLI into two speeds: `--preset pr` (scanners + Fast Brain heuristics, < 2s, zero LLM) and `--preset release` (deep multi-role).

### How to run it

```bash
pipx install "repolens-audit[scanners]"

# Instant deterministic check
repolens review --scanners-only

# Import graph & cyclicity ratchet
repolens check --diff

# Preview planned packs before running Slow Brain
repolens plan
```

- **GitHub Repository:** https://github.com/vksvicky/RepoLens
- **Playbooks & Engineering Resources:** https://cycleruncode.club

I'd love feedback from other developers, consultants, and platform leads. Roast the architecture, try it on your own repos, or check out the code.
