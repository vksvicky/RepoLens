# Recipe: First-week operator path (audit → evidence → fix)

**Audience:** Someone installing RepoLens for the first time who wants a credible due-diligence loop in week one — not a full ASPM platform tour.

**Related:** [which-command.md](../which-command.md) · [setup-ai-and-scanners.md](../setup-ai-and-scanners.md) · [sample report](../../reports/samples/sample_audit_report.md) · [docker.md](../docker.md) · [SARIF unification](./sarif-unification.md)

---

## Honesty up front

| Path | Use when | Expect |
|------|----------|--------|
| **BYOK** (Bedrock / Vertex / Gemini / Anthropic / OpenAI…) | Day-to-day deep audits | Minutes–tens of minutes per change-set; best quality |
| **Ollama air-gap** | Policy forbids cloud keys | Often **1–3+ hours** for full deep on mid hardware — not a “fast local” substitute |
| **`--preset pr` / scanners-only** | Every PR CI gate | Seconds–minutes; **no** Slow Brain narrative |

Install: `pip install "repolens-audit[scanners]==0.1.2"` (or editable clone). Primary zero-infra story stays **pipx/pip**, not Docker.

Not sure which flags to pass? Ask the catalog, then run the line it prints:

```bash
repolens which pr       # fast gate, no model
repolens which changed  # review what you just changed
repolens which audit    # full due diligence
```

`--explain` adds one line on why. The Markdown report records that command under Provenance, plus the expanded flags, so someone else can re-run it.

---

## Day 1 — See a gate without burning tokens

```bash
# Deterministic PR gate (scanners + Fast Brain + ratchet; no LLM)
repolens review --path . --out reports --preset pr --fail-on HIGH --ci

# Or the due-diligence alias (same stack + release-oriented defaults)
repolens audit --path . --out reports --preset pr
```

Open `reports/` Markdown/JSON. Optional: fold existing CodeQL/Sonar/ESLint SARIF — [sarif-unification.md](./sarif-unification.md).

---

## Day 2–3 — One deep pass on what changed

```bash
# Prefer BYOK env vars from setup guide; budget a timeout
repolens audit --path . --out reports --changed --deep --timeout 900

# Board-ready artefacts from the latest report
repolens export --evidence-pack --out reports
repolens export --executive-summary --out reports
```

Compare two audits for client drift:

```bash
repolens diff-audit reports/before.json reports/after.json --format html -o reports/drift.html
```

---

## Day 4 — Remediate with grounding

```bash
# Grounded single-file patch (refuses multi-file self-heal)
repolens fix <finding-fingerprint> --patch

# Before you touch a hot module
repolens blast-radius path/to/module.py
```

Browse interactively (stdlib HTML, no extra server deps):

```bash
repolens view reports/latest.json
```

---

## Day 5 — CI + portfolio + container (optional)

```bash
# Soft-fail batch over many clones
repolens portfolio --paths-file repos.txt --out portfolio-out

# Locked-down runners: pull the slim image (pinned scanners; no baked keys)
# ghcr.io/vksvicky/repolens:0.1.2 — see docs/docker.md
```

Wire `--preset pr` into GitHub Actions / GitLab / CodeBuild using [ci.md](../ci.md) and [docker.md](../docker.md).

---

## Checklist

- [ ] PR gate green with `--preset pr` (no LLM)
- [ ] One BYOK deep audit on a real change-set
- [ ] Evidence pack + executive summary reviewed by a human
- [ ] At least one `fix --patch` applied and re-audited
- [ ] CI recipe chosen (pipx **or** GHCR) — not both required
