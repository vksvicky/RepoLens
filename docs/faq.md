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
| **Does AI review every file?** | **No (Slow Brain).** LLM sample defaults to top **200** files. **Fast Brain** heuristics run on a much larger matched set (default 10k). Scanners walk the **full** tree. See [Two-Lane / inventory](#how-does-the-200-file-inventory-cap-work-are-the-other-files-at-risk). |
| **Which UUID for `explain`?** | Copy the **Fingerprint** (preferred). **Occurrence** also works. See [finding fields](#what-do-finding-fields-mean). |

Longer narrative: [design/ai-keys-scanners-and-local-learning.md §5](./design/ai-keys-scanners-and-local-learning.md#5-decision-summary-plain-language).  

**Setup steps for all three options:** [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) (cloud key · local Ollama · scanners only).

---

## How does the 200-file inventory cap work? Are the other files “at risk”?

**Two-Lane product (Phase 6.11):**

| Lane | Default scope | Role |
|------|---------------|------|
| **Fast Brain** | Up to **10 000** matched files (`[fast_brain].max_files`; `0` = uncapped) | Parallel regex/line/stat heuristics + domain packs; fingerprints |
| **Slow Brain** | Top **200** (`[general].max_files`) | LLM deep / single-shot sample; `--ci` triage often fewer (hit files only) |
| **Scanners** | **Full tree** | gitleaks / Semgrep / OSV / Trivy / Checkov |

**Yes — for the LLM narrative** the rest of the tree is unreviewed by the model. **No — for Fast Brain + scanners** on typical repos under the Fast Brain cap.

**How priority order is chosen** (both lanes share the same sort, then different caps):

1. Walk the tree (skip `.git`, `node_modules`, `reports`, binaries, etc.).
2. Drop files over ~200 KB.
3. Assign a **priority band** from path/name hints (`security`, `auth`, `jwt`, `secret`, … → band 1; controllers/services → band 2; else band 3).
4. Sort by `(priority_band, path)`; Fast Brain keeps up to its cap; LLM pool is the first `general.max_files`.

Fast Brain heuristics are **not** AST parsers (that stays Slow Brain or Semgrep). Progress shows Fast vs Slow counts; provenance has `fastBrainFiles` / `llmPackFiles`.

### Org / multi-project reality

| Concern | Honest answer |
|---------|----------------|
| 5k–50k file monorepo | LLM pack is a **sample** (often &lt;1%), not enterprise “we reviewed everything” |
| Remaining files “at risk”? | **For AI narrative — yes, unreviewed.** For secrets/CVE/SAST — scanners still cover the full tree when enabled |
| Many repos to check | Deep local LLM is often **≥1 h per ~200-file pack** (hours on larger packs). That does not scale as “run full deep on every project tonight” |
| What to run day-to-day | `--scanners-only` or `--ci --fail-on HIGH` (LLM bypass when scanners clean) |
| When to run deep LLM | Scheduled / release audits, or hot-path packs (`--changed`, triage hits) — not every PR |
| Raise `max_files` alone? | Makes deep runs **longer**; does not by itself create safe full-repo AI coverage |

Do **not** position RepoLens as replacing CodeQL/Semgrep/Dependabot fleet coverage. It adds a structured dual-review layer on a **prioritised slice**, plus optional full-tree scanners.

Reports and the CLI summary now open with a **Two-Lane** headline (Fast Brain file count ± lane seconds · Slow Brain pack or “bypassed” · duration · severity counts). Use it to sanity-check that lane scopes match what you intended.

Related: [command-atlas.md](./command-atlas.md) · [command atlas durations](./command-atlas.md#7-approximate-duration) · [fair dogfood recipe](./command-atlas.md#fair-two-lane-dogfood-patternsorcerer-class).

---

## What is a fair dogfood recipe for Two-Lane speed?

When demoing or comparing RepoLens to other tools on a PatternSorcerer-class repo (~200–800 reviewable files), **do not lead with `--full`**. That forces a full Slow Brain pack even when adaptive mode would shrink it — a warm run on local **32B** can still sit around **~1 hour**, which is an unfair “speed” story.

| Goal | Prefer | Expect |
|------|--------|--------|
| Show Two-Lane scope honestly | `--ci` triage **or** default adaptive (no `--full`) | **Fast Brain** ≈ whole matched tree (up to cap); **Slow Brain** ≈ triage hit files or pack cap — check the **Two-Lane** headline |
| PR-style gate | `repolens review --ci --fail-on HIGH …` | Often **Slow Brain bypassed** when scanners are clean at the floor |
| Release / forced full LLM sample | `--full --deep --timeout 3600` | Slow Brain ≈ `general.max_files`; budget time |

**Latency honesty:** Fast Brain heuristics finish in **seconds** on typical trees. A local **qwen2.5-coder:32b** Slow Brain pass is still usually **much slower** than a cloud **Claude Haiku**-class API on the same pack — model size and prompt eval dominate, not “RepoLens overhead”. For apples-to-apples **quality** demos, compare cloud-to-cloud or local-to-local; for **CI speed**, use `--ci` or `--scanners-only`.

Copy-paste recipes: [command-atlas.md § Fair Two-Lane dogfood](./command-atlas.md#fair-two-lane-dogfood-patternsorcerer-class).

---

## How is RepoLens different from prompt-paste review tools?

| | RepoLens CLI | Prompt-paste / chat workflows |
|--|--------------|-------------------------------|
| Output | Structured gate reports, SARIF, CI exit codes | Text in a chat thread |
| Remediation | **`repolens explain`** — symbol **moves**, import **diffs**, outline evidence, Mermaid (grounded in the repo) | You copy suggestions by hand |
| Scanners | Optional gitleaks / Semgrep / OSV / Trivy on the **full tree** | Usually none unless you paste scanner output yourself |
| Grades | **Gate / band confidence** = review-package adequacy — **not** “% secure” and **not** cross-repo percentile ranks | Some SaaS tools show population percentiles — RepoLens does **not** (privacy-first local CLI; no central corpus) |

Playbooks in chat and RepoLens share review *ideas*; they are not the same product surface. See [using-playbooks.md](./using-playbooks.md).

---

## Do scanners catch missing `.gitignore` rules?

**Usually no — and we do not claim they do.** **gitleaks** (and similar) find **secret content** already present in the tree. **Missing `.env` / credential patterns in `.gitignore`** come from **Fast Brain heuristics** (`heuristic.gitignore_secrets`, etc.) — deterministic pattern checks, not a live secret scan. Treat those rows as hygiene hints; confirm with your policy and scanners. Heuristic and LLM twins on the same theme (e.g. gitignore + `sec.repo_hygiene_secrets`) are **clustered** so the report does not list three near-identical `.gitignore` issues.

---

## What is the adaptive cache (Phase 5)?

On each review RepoLens can maintain `.repolens/repolens.sqlite` (local): file fingerprints + run timings + optional FTS content (opt-in). Later runs prefer **changed + P1** files (`adaptive.mode=auto`), and store a **recommended timeout** per project.

| Flag / config | Effect |
|---------------|--------|
| *(default)* `adaptive.mode=auto` | Warm re-review: smaller LLM pack (changed + hot paths) |
| `--changed` | LLM pack = added/changed only; if none, **reuse last successful LLM** snapshot from `.repolens/` (merge fresh scanners) — not newest `reports/*` |
| `--full` | Force full LLM pack (ignore adaptive selection) |
| `--timeout N` / `REPOLENS_TIMEOUT` / `[model].timeout_seconds` | Explicit timeout — **always wins** over the recommendation |
| `repolens adaptive status --path .` | Fingerprints, pending diff, recommended timeout |
| `[adaptive] enabled = false` | Disable fingerprint cache / pack selection |

**Timeout resolution order:** CLI `--timeout` → `REPOLENS_TIMEOUT` → explicit `[model].timeout_seconds` → `meta.recommended_timeout_seconds` (from prior runs) → provider default (Ollama 900s, cloud 120s). Timeout is a **wall-clock** limit for the LLM stream (not only idle-between-chunks).

**Important:** with `adaptive.mode=auto`, if fingerprints show **no added/changed files**, RepoLens still takes a **full LLM pack** (avoids under-reviewing). That is why a “warm” PatternSorcerer run can still be ~1h on a local 32B. For a true smoke:

| Goal | Command |
|------|---------|
| Unit only (seconds) | `python -m pytest tests/test_themes.py tests/test_report.py -q` |
| Scanners only (minutes) | `repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only` |
| LLM only if files changed (else reuse last AI findings) | `repolens review --path "$TARGET" --out "$TARGET/reports" --changed --deep --timeout 900` |
| Force full pack (slow) | `repolens review --path "$TARGET" --out "$TARGET/reports" --full --deep --timeout 3600` |
| Full audit + Extended themes | add `--full-audit` (slowest) |

Fingerprints never store file contents. FTS content learning stays opt-in (`repolens learn` + consent). Design: [phase-5-adaptive-cache-and-recommendations.md](./design/phase-5-adaptive-cache-and-recommendations.md).

---

## What is deep coverage?

**Deep mode** (default **on** for LLM runs) runs heuristics, then chunked P1→P3 passes with a **rules registry** checklist (coverage IDs), and merges/dedupes into one report. Use `--no-deep` for a single-shot LLM call (faster, thinner on large repos).

| Flag / config | Effect |
|---------------|--------|
| *(default)* / `--deep` | Multi-pass deep coverage + heuristics + coverage tally |
| `--no-deep` | Single-shot LLM (legacy thin path) |
| `--full-audit` | Deep **and** full architecture checklist + scores |

## What language do reports use?

Report chrome (Metrics, Coverage, About, Disclaimer) and LLM/heuristic finding prose are written in **British English** (e.g. behaviour, organise, analyse, prioritise). Prompts instruct the model accordingly; code identifiers and paths stay as in the repo.

## How do we harden RepoLens against its own dogfood noise?

Self-review on this repo should not drown in agent scratch (`.superpowers/`), heuristic fixtures, or pedagogical “password” mentions in playbooks. Plan: [superpowers/specs/2026-08-05-self-review-hardening-design.md](./superpowers/specs/2026-08-05-self-review-hardening-design.md) · [implementation plan](./superpowers/plans/2026-08-05-self-review-hardening.md).

## What do finding fields mean?

Each issue in the Markdown / JSON report is a structured finding. Plain meanings:

| Field | Means | Typical use |
|-------|--------|-------------|
| **Severity** | How bad if true: `CRITICAL` → `LOW` | `--fail-on`; triage floor |
| **Priority** | Review band: **P1** security · **P2** bugs/reliability · **P3** architecture/quality | Report section; dual-review order |
| **File** / **Line** | Where the tool believes the issue is | Open in editor; SARIF when verified |
| **Category** | Rule / theme id (e.g. `heuristic.mega_file`, `sec.injection`, `gitleaks`) | Grouping; suppressions by `file`+`category` |
| **Fingerprint** | Identity of the *issue* across runs (from category + file + title). JSON field: `stableId`. | **Prefer this** for `repolens explain`, ignore, and `feedback down` |
| **Occurrence** | This *appearance* in tonight’s report only. Changes every run. JSON field: `runId`. | Optional; also accepted by `explain` if you copied that UUID |
| **Source** | Who produced it: `scanner` · `heuristic` (Fast Brain / packs) · `llm` | CI `--fail-on` often prefers scanners; honesty about provenance |
| **Location** | Whether `file`+`line` was verified against disk (`anchorQuote` / scanner evidence) | Unverified → omitted from SARIF (GitHub won’t get a bad line) |
| **Explanation** | Why this matters in *this* codebase | Human review |
| **Impact** | What goes wrong if unfixed (required for Critical/High) | Risk communication |
| **Recommended fix** | What to do | Remediation |
| **Code example** | Concrete fix snippet (required for Critical/High) | Copy/adapt |
| **Fix timing** | `immediately` · `before launch` · `after launch` · `if time permits` | Planning |
| **OWASP** / **CWE** | Optional taxonomy tags when the model/scanner supplies them | Mapping to standards |

### Fingerprint vs Occurrence — which UUID for `explain`?

**Yes — you can use either.** There is no third “explain UUID.”

| You copy… | Works with `explain`? | Prefer when… |
|-----------|----------------------|--------------|
| **Fingerprint** | Yes | Everyday use — same value next week; also for ignore / feedback |
| **Occurrence** | Yes | You only want *this* report’s row (advanced / debugging) |

Default habit: **always copy Fingerprint.**

Lookup order inside RepoLens: match **Occurrence** (`runId`) first if present, else **Fingerprint** (`stableId`).

JSON still uses `stableId` / `runId` for compatibility; Markdown shows the human labels above.

Schema: [design/cli-and-report-schema.md](./design/cli-and-report-schema.md) · design: [superpowers/specs/2026-08-04-phase-6-issue-explain-diagrams-design.md](./superpowers/specs/2026-08-04-phase-6-issue-explain-diagrams-design.md).

## How do I deep-dive one finding (Phase 6 explain)?

Copy the finding’s **Fingerprint** (or **Occurrence** — both work). After a review:

```bash
# preferred — Fingerprint from the report
repolens explain a08697ac-a881-53ca-a8a0-92d86ca3da5b --path "$TARGET" --out "$TARGET/reports"

# also fine — Occurrence from the same finding
repolens explain caf11d8b-559f-4fd7-a936-16d4681783b6 --path "$TARGET" --out "$TARGET/reports"

# or during review:
repolens review --path "$TARGET" --out "$TARGET/reports" --explain <fingerprint-or-occurrence>[,…]
```

Writes `reports/explain_<short>_<stamp>.md` with problem, impact, **actionable** solutions (symbol moves + import diffs when splitting), structure outline evidence, and a Mermaid diagram grounded in real symbols. Toggle: `[explain]` in config.

Progress (default on): phase lines + `… still waiting` heartbeats while the model runs (`-v` for detail, `-q` quiet, `--heartbeat 0` to disable). Diagrams never fail the command. A note about optional PNG/SVG only means image render was skipped — the Mermaid fence still works in GitHub / IDE preview.

For `heuristic.mega_file`, RepoLens feeds a **symbol outline** (classes/functions + line spans) so the model cannot invent `UI_module` / `IO_module`-style fluff; generic boilerplate answers are rejected and replaced with an outline-guided fallback.

## How do we reduce known LLM false positives for everyone?

Post-parse **FP calibrations** (default on) demote patterns such as list-form `subprocess` “command injection”. Toggle under `[deep].fp_calibrations` in config / `.repolens.toml` (e.g. `subprocess_list_not_injection = false` to disable). Design: [superpowers/specs/2026-08-05-fp-calibrations-config-design.md](./superpowers/specs/2026-08-05-fp-calibrations-config-design.md).

---

## What do report metrics mean? (confidence vs security)

**`Confidence` / gate confidence is not “% secure”, not an architecture grade, and not a cross-tenant percentile** (no “better than 73% of repos”). It is how sure RepoLens is that *this review package* (findings + coverage + scanners) is adequate for a gate-style decision. Models often self-report high numbers; Phase **5.1** recalibrates that with coverage penalties and adds band-specific metrics.

| Metric | Means | Does **not** mean |
|--------|--------|-------------------|
| **Gate confidence** | Adequacy of the overall review package (weakest scored band, then coverage penalties) | App is 47% / 95% “secure” or well-architected |
| **Security audit confidence** | Honesty/completeness of the **P1 / `sec.*`** checklist + scanners, **reduced** when Critical/High **security** findings remain (P1 or `sec.*` / scanner cats) | A CleanVibes-style “% secure” posture score, or CVE completeness |
| **Reliability audit confidence** | Honesty/completeness of the **P2 / `rel.*`** checklist, minus open Critical/High in that band | “App is X% reliable” |
| **Architecture audit confidence** | Honesty/completeness of the **P3 / `arch.*`** checklist, minus open Critical/High in that band | The 1–10 architecture `scores` block |
| **Critical / High / Medium / Low** | Finding severity counts (all bands) | Confidence % |
| **Coverage** covered / N/A / missed | Checklist accountability for deep-mode rule ids | “N/A = ignored forever” — lazy N/A are rejected in 5.1 |
| **Theme breakdown** | Per-theme covered / N/A / missed + finding counts | “% clean” per theme |
| **Duration** | Wall-clock for the whole command | Per-pass LLM time alone |

### Coverage: covered vs N/A vs missed

Deep mode asks the model (plus heuristics) to account for each checklist id in the rules registry (`sec.*`, `rel.*`, `arch.*`, …). Progress lines like `Coverage: 11 covered · 9 N/A · 2 missed` mean:

| Status | Meaning | Example from a CLI-tool dogfood |
|--------|---------|----------------------------------|
| **Covered** | The id was addressed (issue filed and/or explicit coverage note) | `sec.injection`, `arch.structure_size` |
| **N/A** | Honestly out of scope for *this* codebase, with a reason | `sec.xss_csrf` — no web request/response surface |
| **Missed** | In scope for the pass, but neither covered nor a valid N/A | `arch.consistency_style`, `arch.blast_radius` |

N/A is **good** when true (don’t invent web XSS findings for a pure CLI). Missed **lowers** gate / band confidence. Full lists appear under **## Coverage** in the Markdown report (and Theme breakdown maps the same ideas to product themes).

### How the % numbers are calculated (Phase 5.1)

Implementation: `src/repolens/metrics.py`.

1. Each deep pass returns a **base confidence** (model self-score for that pass).  
2. **Band audit %** (security / reliability / architecture) starts from that pass’s base, then:
   - **−4** per **missed** coverage id in that band (`sec.` / `rel.` / `arch.`), capped at −40  
   - **−3** per **invalid/lazy N/A** remapped to missed in that band, capped at −30  
   - Security only: **+5** if every requested scanner status is `ran`  
   - **−20** per open Critical and **−10** per open High attributed to that band (caps −60 / −50)  
3. **Gate confidence** = **minimum** of (ran pass bases + scored band audits), then apply the same missed / invalid-N/A penalties **globally** (only for ids in scored bands), clamp 0–100.

Worked sketch (numbers like a local deep `review` on RepoLens itself):

- Security audit **100%** — P1/`sec.*` checklist looked complete, scanners all ran (+5), and **no** Critical/High counted as *security* (P1 or `sec.*`). High findings tagged `rel.*` or `arch.security` with priority P2 do **not** reduce the security band.  
- Reliability **55%** / architecture **67%** — lower because of missed ids and/or Critical/High in those bands (e.g. High `rel.error_recovery`).  
- Gate **47%** — pulled down by the **weakest** of those scores, then any global missed-id penalty (here: 2 missed → up to −8).

So: **high security audit + low gate** is normal when reliability/architecture (or coverage misses) are the weak link — gate is deliberately the “can I trust this package?” floor, not a security grade.

### Core vs Extended themes (Phase 5.2)

Deep reports include a **Theme breakdown** section:

| Pack | When shown | Examples |
|------|------------|----------|
| **Core** (18) | Every deep `review`; `sentinel` shows Core **P1 / `sec.*`** only | Structure & size, duplication, secrets hygiene, injection, auth, TLS, `rel.*` reliability themes |
| **Extended** (~19) | `--full-audit` (else omitted from the table; honest N/A when out of scope) | Database, a11y, observability, IaC, privacy/PII, build/release integrity |

Heuristics (mega-files, sibling duplication, gitignore/secrets, CI gaps, …) map into theme finding counts. Deprecated ids such as `sec.secrets` / `sec.deps_config` alias to the new theme ids so older N/A notes still resolve. Themes are **not** a substitute for Semgrep/OSV/gitleaks/CodeQL.

Design: [phase-5.2-theme-coverage-and-report-breakdown.md](./design/phase-5.2-theme-coverage-and-report-breakdown.md) · [phase-5.1-deep-hardening.md](./design/phase-5.1-deep-hardening.md). Config: `[deep]` (`enabled`, `chars_per_pass`, `mega_file_lines`, `mega_file_exclude_globs`).

**Rules** load by **id** from a registry (project `.repolens/rules/` → user config → packaged defaults)—not hard-coded Markdown paths on the author’s machine. Override a rule with `.repolens/rules/<id>.md`.

If the model returns invalid JSON, RepoLens still writes a report (scanners + heuristics + any salvageable issues) and exits **0**.

**Cloud tip (Phase A):** OpenAI / Anthropic / DeepSeek / `openai_compatible` use the **same `--deep` pipeline** as Ollama — provider choice is quality/cost/privacy, not a separate review path. Pick via `repolens init --provider …`. Heartbeats stream completion chars for all of these (Ollama also shows `/api/ps` load). Named aliases for Azure/Groq/etc. are **Phase 8**; native Gemini/Bedrock are **Phase 9**.

Guided wizard: `./scripts/repolens-guided.sh` prompts for deep (default **Y** on review / full-audit).

---

## Do I need `--full-audit` every time? (review profiles)

**No.** Full audit runs deep P1→P2→P3 with the full architecture checklist — often **30–60+ minutes** on a 32B local model and a ~180-file pack. Use profiles:

| Goal | Suggested command | Typical cost (32B local, large pack) |
|------|-------------------|--------------------------------------|
| Verify metric / security band only | `repolens sentinel …` (P1 only) | ~1 deep pass |
| Day-to-day / PR delta | `repolens review --changed …` | Often skips LLM if no file delta; else smaller pack |
| Normal dual review | `repolens review …` (deep on, **no** `--full-audit`) | 3 passes, scoped P3 |
| Release / milestone | `repolens review --full-audit …` | 3 passes + full arch + scores |
| Fast scanners only | `repolens review --scanners-only …` | Seconds–minutes |
| Thin single-shot | `repolens review --no-deep …` | 1 LLM call (weaker coverage) |

To check the **security audit confidence** fix without a 40‑minute full audit: run **`sentinel`** (or `review` without `--full-audit`).

---

## Which model should I use? (quality vs time vs machine)

Findings quality is mostly **model + pack size**, not CPU brand alone. Apple Silicon (M4) is strong for local LLMs; **unified memory** and model size dominate wall time.

| Setup | Quality (depth / adherence) | Speed | Notes |
|-------|----------------------------|-------|-------|
| Cloud Claude / GPT (Phase A) | Highest for checklist prose | Minutes | BYOK; same `--deep` pipeline |
| Local **32B+** coder (e.g. `qwen2.5-coder:32b`) | Strong local | Slow (tens of min / pass) | Needs ~24–48 GB+ unified memory comfortably |
| Local **14B** | Medium | Medium | Good daily driver on 16–24 GB |
| Local **7B** | Thinner / more N/A | Faster | Prefer `--changed` / smaller packs; heuristics still help |
| `--scanners-only` | No LLM narrative | Fast | Complements, does not replace playbook review |

**Rough local guidance**

| Machine RAM (unified / system) | Prefer | Avoid for full-audit packs |
|-------------------------------|--------|----------------------------|
| ≤16 GB | 7B, deep + `--changed`, or cloud | 32B full-audit on large repos |
| 24–36 GB | 14B daily; 32B for sentinel / scoped review | Frequent 32B `--full-audit` |
| 48 GB+ (e.g. high-spec M4) | 32B deep review OK; full-audit for releases | Expect 30–60+ min on large packs anyway |

Guided script warns when a large model is paired with a likely full pack. Timeouts: 7B ~900s, 14B ~1800s, 32B ~3600s per HTTP call (see guided helpers).

---

## What does “still waiting” mean during a deep pass?

Today each LLM pass is a **blocking HTTP** request (not token-streaming yet). The heartbeat shows:

- which deep pass (p1/p2/p3) and model/provider  
- prompt size / file count / coverage ids  
- for Ollama: best-effort `/api/ps` (model loaded / idle)  

It does **not** yet show “% tokens generated”. Streaming progress is a follow-up improvement.

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
| **CVE / SCA** | “Are dependencies known-vulnerable?” | OSV-Scanner and/or Trivy (`--scanners` / plugins) |
| **SBOM / licenses** | “What is in the inventory?” | Trivy CycloneDX (`[scanners] sbom` / `licenses`) when Trivy is installed |
| **Your CI** | “Is this enforced on every PR?” | Dependabot, CodeQL, Snyk, etc. — we *call out gaps*, we don’t replace them |

**Important:** The LLM layer is **not** a CVE database and **must not** invent a dependency graph or claim reachability from lockfile reading. Vulnerable package / CVE facts come only from scanner JSON (OSV/Trivy). For audit-grade **CVE** lists and SBOM artifacts, enable those scanners (or your existing SCA in CI). “OWASP compliant” is not a certification we stamp; we **align findings** to OWASP Top 10 / CWE and recommend deterministic scanners for evidence packs.

### Reachability (Phase 6.9 honesty)

RepoLens does **not** ship Snyk-class call-graph reachability. Free scanners rarely expose a true “hits production” bit; when they do not, we never invent one.

What we do (best-effort):

- Surface **scanner-owned** SCA fields (package, installed/fixed version, advisory id)
- Optional **usage hint**: does the package name appear in project source (import/require/text)? Labelled explicitly as *not reachability*
- Near-duplicate **clustering** to reduce noise
- Opt-in `--verify-findings` / `[deep].verify_findings`: re-check Critical locations; failures only annotate — they never block the report

Turn hints/clustering off with `[deep] usage_hints = false` / `cluster_duplicates = false`.

**Named checklist themes (Phase 6.5)** include SSRF, path traversal / Zip Slip, XXE, NoSQL injection, ReDoS, log injection, weak PRNG, JWT pitfalls, rate limiting, and supply-chain integrity — in addition to classic injection/XSS/secrets. Naming them does **not** claim CodeQL/Checkmarx rule parity.

### Domain packs (Phase 6.10)

Optional niche packs (e.g. `azure-sentinel` for Logic Apps / SOAR) are **off by default**. Enable with `--pack <id>` or `[packs] enabled = […]`. They add a playbook slice plus light heuristics; they do **not** replace Checkov/ARM-TTK and do **not** change core `repolens sentinel` when disabled. See [packs.md](./packs.md).

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

Longer comparison (Checkmarx, Veracode, Fortify, Semgrep, Trivy, Checkov, GHAS, ZAP, …): [design/repolens-vs-appsec-tools.md](./design/repolens-vs-appsec-tools.md).

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

Security-only mode (P1 playbook). One deep security pass (plus scanners/heuristics) — not a full dual review. Architecture / reliability audit % are **omitted** (N/A), not 0%. Gate confidence reflects the sentinel package only.

Reports are written as `gate_review_report_sentinel_YYYY-MM-DD_HHMM.md` so they do not overwrite a prior `review` report. Full dual review remains `repolens review`.

## Why do wait lines say “still waiting” for so long?

Local 32B models often spend minutes on **prompt evaluation** before the first output token. Heartbeats stream completions and show **chars/chunks received** (plus Ollama `/api/ps` when local). Until the first token arrives, “waiting for first token (prompt still evaluating)” is expected — not a hang.

Each report also records **Duration** (wall clock for the whole command).

## Which BYOK / cloud providers are supported?

| `repolens init --provider` | Key env | Transport | Streamed wait UX |
|----------------------------|---------|-----------|------------------|
| `openai` | `OPENAI_API_KEY` | OpenAI chat completions | Yes |
| `anthropic` | `ANTHROPIC_API_KEY` | Anthropic Messages API | Yes |
| `deepseek` | `DEEPSEEK_API_KEY` | OpenAI-compatible | Yes |
| `openai_compatible` | `REPOLENS_API_KEY` | Your `--base-url` (Azure, Groq, OpenRouter, LM Studio, …) | Yes |
| `ollama` | _(none)_ | Local OpenAI-compatible | Yes + `/api/ps` |
| `none` | — | No LLM | N/A |

**Planned (not shipped yet):**

| Phase | What |
|-------|------|
| **Phase 8** | Named aliases + recipes: Azure OpenAI, Mistral, Groq, OpenRouter, LM Studio/vLLM, … ([design](./design/phase-8-provider-aliases-and-recipes.md)) |
| **Phase 9** | Native SDKs where needed: Gemini/Vertex, Bedrock, … ([design](./design/phase-9-native-provider-sdks.md)) |

Until then, many hosts work via `openai_compatible` + `--base-url`. See [setup-ai-and-scanners.md](./setup-ai-and-scanners.md).

---

## Will RepoLens auto-push my code?

No. It produces reports and exit codes. Git push stays under your control.

---

## How do I export a PDF?

Prefer Markdown reports, then:

```bash
pandoc reports/gate_review_report_review_YYYY-MM-DD_HHMM.md -o report.pdf
```

or Print → Save as PDF from a Markdown preview.

---

## Is LLM-only review enough for production?

No. Use RepoLens as a due-diligence layer **plus** tests, CI, and mature scanners (CVE/SAST/secrets). See [phases.md](./phases.md) Phase 3 and the design note above.

## Does RepoLens export SARIF for GitHub / Sonar?

Yes (`--sarif`, Phase 6.4). Export is **anchored**: scanner locations are trusted; LLM/heuristic findings need a resolvable `anchorQuote` in the cited file. Unverified locations stay in Markdown/JSON only — never in SARIF — so GHAS highlighting is not fed hallucinated lines. See [ci.md](./ci.md#anchored-sarif--sbom-phase-64--62).

## How do I stop the same finding failing every PR?

Use **Phase 6.7 suppressions**:

1. Copy the finding’s **Fingerprint** from the report (JSON: `stableId`).
2. `repolens feedback down <fingerprint> --reason false_positive --path .` (writes `.repolens-ignore`), **or** add an `[[ignore]]` table by hand.
3. For LLM/heuristic line noise only: `# repolens:disable-next-line` above the line (scanners still need an ignore entry).

Suppressed rows leave fail-on and SARIF, but stay listed under **Suppressed** in Markdown. See [rules.md](./rules.md#suppress-a-finding-so-it-stops-nagging-phase-67).

`feedback down` also logs local events used for soft FP calibrations (LLM/heuristic only). Optional Critical consistency: `[deep].critical_consistency = "heuristic"` or `"llm"` (default off).

## Do you publish detection F1 / “beats Semgrep” numbers?

No as a marketing lead. Phase 6.6 pre-registers a methodology that leads with **remediation rate**, **MTTR**, and **suggested-fix apply %** — not synthetic F1 alone. See [benchmarks/methodology.md](./benchmarks/methodology.md) and the honest MVP table ([results](./benchmarks/results/mvp-2026-08-06.md)). Supporting readiness metrics: `repolens score-report path/to/report.json`.

## How do Critical/High suggested fixes show up on a PR?

On GitHub Actions (Phase 6.8), the RepoLens Action appends a **PR summary** to the job summary and emits `::error` / `::warning` annotations for Critical/High (with code examples in the summary). Locally: `repolens pr-summary --reports-dir reports`. RepoLens does **not** auto-commit fixes or post review comments via the GitHub API. See [ci.md](./ci.md#pr-suggested-fix-summary-phase-68).

## How does `--ci` triage routing work?

On PRs, prefer **`repolens review --ci --fail-on HIGH`** (Action `ci: true` by default):

1. Scanners run first (in parallel when multiple).  
2. If no scanner findings at the severity floor → **LLM is bypassed** (report still written).  
3. If there are hits → LLM runs on **hit files only** (not a full-repo deep).  
4. `--fail-on` gates on **scanner** findings; LLM/heuristic rows do not sole-fail the build.

Use full `--deep` for scheduled/release audits. See [ci.md](./ci.md) and [phase-6.x §6.3](./design/phase-6.x-scanner-depth-ci-gates-and-credibility.md).

## Can we use this in corporate CI/CD (Jenkins, email, dashboards)?

**Local + GitHub Actions / Bitbucket artifacts:** documented and usable now with `--ci` triage ([ci.md](./ci.md)).

**Jenkins, CircleCI, email, internal dashboards:** planned as **Phase 7** — design sketch in [design/phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md). Pattern: run on the CI agent → archive `reports/**` → notify or ingest JSON into *your* tools. RepoLens does not ship a hosted dashboard.

---

---

## How does RepoLens analyse a repository?

See **[ADR-01: Analysis runtime architecture](./adr/01_analysis_runtime_architecture.md)** for pipeline diagrams. Colour legend: [adr/_diagram_legend.md](./adr/_diagram_legend.md).

---

## Where is the roadmap?

[phases.md](./phases.md).

---

## Disclaimer (AI / LLM output)

**Short answer:** RepoLens may use AI/LLMs (plus heuristics and optional scanners). Treat every finding and suggested fix as **unverified**. The authors do **not** take responsibility for decisions or damage resulting from AI/LLM or tool-assisted output.

Every Markdown gate report ends with a **Disclaimer** section. In plain terms:

- Output can be incomplete, incorrect, outdated, or unsuitable for your environment.
- Software and reports are provided **as is**, without warranty.
- **You** remain solely responsible for review, validation, risk assessment, and what you ship.
- Authors accept **no liability** for loss, security incidents, or other consequences from reliance on that output.
- A RepoLens report is **not** a certification, penetration test, legal opinion, or paid professional audit.

This sits alongside the [MIT licence](../LICENSE) “AS IS” terms.
