# RepoLens command atlas (holy grail)

One place for **install → run this → expect that → if odd, fix it**, with rough timings.
Deep guides stay linked; this page is the map.

| Need | Go here |
|------|---------|
| Paths / OS install detail | [try-on-your-repo.md](./try-on-your-repo.md) |
| Cloud vs Ollama vs scanners-only | [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) |
| **Fast Brain vs Slow Brain** (which flags, what to expect) | [§ Fast Brain vs Slow Brain](#fast-brain-vs-slow-brain-commands--examples) |
| Scanner plugins | [scanners.md](./scanners.md) |
| CI / GitHub Action | [ci.md](./ci.md) |
| Domain packs detail | [packs.md](./packs.md) · [packs-quickcheck.md](./packs-quickcheck.md) |
| Suppressions / rules | [rules.md](./rules.md) |
| FAQ | [faq.md](./faq.md) · [finding fields](./faq.md#what-do-finding-fields-mean) |

**How to read this page**

- Tables are **Command / Recipe → Expect → Example**. Copy the **Example** column; swap `TARGET` for your repo path.
- Progress lines (`→ …`) show by default; **`-v`** adds detail; **`-q`** is quiet (CI).
- Exit codes (typical): **0** ok · **1** `--fail-on` threshold hit · **2** usage/config/missing required scanner · **3** clone/source failure.
- Durations are **order-of-magnitude**, not SLAs (disk, cold Semgrep cache, network, model size all move the needle).

---

## 1) Install

### From a RepoLens clone (dogfood / contributors)

| OS | Commands |
|----|----------|
| macOS | `cd /Users/[username]/Development/RepoLens` → `python3 -m venv .venv` → `source .venv/bin/activate` → `pip install -e ".[dev]"` |
| Linux | Same with `/home/[username]/Development/RepoLens` |
| Windows (PowerShell) | `cd C:\Users\[username]\Development\RepoLens` → `py -3.11 -m venv .venv` → `.\.venv\Scripts\Activate.ps1` → `pip install -e ".[dev]"` |

Optional Semgrep via pip: `pip install -e ".[dev,scanners]"`. What extras mean: [install-extras.md](./install-extras.md).

### First checks

| Command | Expect | Example |
|---------|--------|---------|
| `repolens version` | Version string (e.g. `0.1.0a1`) | `repolens version` |
| `repolens --help` | Command list including `review`, `sentinel`, `plugins`, `packs`, … | `repolens --help` |

### Configure once (only if you want LLM narrative)

| Goal | Expect | Example |
|------|--------|---------|
| Local Ollama | Writes `~/.config/repolens/config.toml` | `repolens init --provider ollama` |
| Pin a model | Same config; overwrites with `--force` | `repolens init --provider ollama --model qwen2.5-coder:32b --force` |
| Cloud BYOK | Config file; key stays in env, not in git | `repolens init --provider openai` then `export OPENAI_API_KEY=…` |
| Scanners / dry-run only | No model required | Skip `init`; use `--scanners-only` / `--dry-run` |

### Install scanner plugins (once per machine)

| Command | Expect | Example |
|---------|--------|---------|
| `repolens plugins install all --yes` | Downloads pinned tools under `~/.cache/repolens/tools/` | `repolens plugins install all --yes` |
| `repolens plugins status` | Table: tool → available / missing | `repolens plugins status` |

Platform notes: [scanners.md](./scanners.md). Windows plugin matrix is thinner — dry-run + LLM still work.

### Point at a target repo

```bash
# bash/zsh — no spaces around =
TARGET=/Users/[username]/Development/[your-project]
repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only
```

Remotes: `--github OWNER/REPO`, `--bitbucket WORKSPACE/REPO`, `--hf …`, `--git-url` — see [remote-sources.md](./remote-sources.md).

---

## 2) Start here (setup commands)

| Command | Expect | Example |
|---------|--------|---------|
| `repolens version` | Prints version | `repolens version` |
| `repolens init --provider …` | Creates/updates user config | `repolens init --provider ollama --force` |
| `repolens plugins status` / `list` | Availability table | `repolens plugins status` |
| `repolens plugins install …` | Install messages; re-run `status` | `repolens plugins install gitleaks --yes` |

---

## 3) Review family

`review` = full P1→P2→P3 · `sentinel` = security P1 · `architecture` = architecture / readiness.  
Shared flags unless noted (`--full-audit` is mainly on `review`).

Set once in the shell: `TARGET=/Users/[username]/Development/[your-project]`

### Recipes → what you should see

| Recipe | Expect | Example |
|--------|--------|---------|
| Dry-run inventory | Inventory only; **no** scanners/LLM | `repolens review --path "$TARGET" --out "$TARGET/reports" --dry-run` |
| Scanners-only | Summary + MD/JSON; Fast Brain heuristics | `repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only` |
| Scanners-only verbose | Extra `·` detail (scanners, SBOM, packs) | `repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only -v` |
| CI gate (**fair Two-Lane demo**) | Triage; **`Two-Lane:`** headline; often **`LLM bypassed…`** when clean | `repolens review --path "$TARGET" --out "$TARGET/reports" --ci --fail-on HIGH -q` |
| Adaptive deep (no `--full`) | Fast Brain ≈ tree; Slow Brain ≈ adaptive pack — check headline | `repolens review --path "$TARGET" --out "$TARGET/reports" --deep --verbose --timeout 3600` |
| Force full Slow Brain pack (slow — not a speed demo) | Full LLM inventory; often **≥1 h** on local 32B | `repolens review --path "$TARGET" --out "$TARGET/reports" --full --deep --verbose --timeout 3600` |
| Single-shot LLM | Faster, thinner coverage | `repolens review --path "$TARGET" --out "$TARGET/reports" --no-deep` |
| Changed pack only | Smaller adaptive LLM pack | `repolens review --path "$TARGET" --out "$TARGET/reports" --changed` |
| Domain pack | Pack heuristics in `-v` detail | `repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only --pack azure-sentinel -v` |
| SARIF | Also writes anchored SARIF | `repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only --sarif` |
| Verify Criticals | Location re-check (non-fatal) | `repolens review --path "$TARGET" --out "$TARGET/reports" --verify-findings` |
| Sentinel (P1) | Security-focused report name | `repolens sentinel --path "$TARGET" --out "$TARGET/reports" --scanners-only` |
| Architecture | Architecture playbook path | `repolens architecture --path "$TARGET" --out "$TARGET/reports" --dry-run` |

### Review progress lines (common)

| Line pattern | Meaning | Example (from a real run) |
|--------------|---------|---------------------------|
| Fast brain inventory | Lane 1 file set for heuristics (default cap 10k) | `→ Fast brain inventory: 286 matched file(s)` |
| Slow brain LLM pool | Lane 2 sample when Fast &gt; LLM cap | `· Slow brain LLM pool: top 200 by priority (general.max_files=200)…` |
| Fast brain heuristics | Parallel deterministic lane | `→ Fast brain: heuristics on 286 file(s) (workers=8)…` |
| Dropped from pack | Still on disk; out of fingerprint/LLM view | `· 12 dropped from inventory pack` |
| Removed from tree | Path gone / not a file anymore | `Cache: +0 added, ~2 changed, -1 removed from tree` |
| Scanners finished | Deterministic tools done | `→ Scanners: finished (0 finding(s), 3/3 ran)` |
| LLM bypassed | `--ci` / triage: no LLM spend | `→ LLM bypassed (scanners/heuristics clean at triage floor)` |
| LLM pack | Adaptive / triage file selection | `→ LLM pack: 200/200 file(s) (adaptive mode=full)` |
| Domain packs | Pack heuristics (`-v`) | `· Domain packs enabled: azure-sentinel` |
| Writing report | Artifacts landing | `→ Writing report → reports` |
| Summary metrics | Severity / Fast Brain counts | `Files scanned (Fast Brain) │ 286` · `LLM pack files │ 0` |
| **Two-Lane** headline | Markdown (after metadata) + CLI summary | `**Two-Lane:** Fast Brain: 286 file(s) in 2.1s · Slow Brain: bypassed (triage clean) · …` |

---

## 4) After a report

Copy **Fingerprint** from the gate report (Occurrence also works) — [which UUID?](./faq.md#fingerprint-vs-occurrence--which-uuid-for-explain).

| Command | Expect | Example |
|---------|--------|---------|
| `repolens explain <fingerprint\|occurrence>` | Progress + heartbeats; actionable explain MD (outline for mega-files) | `repolens explain a08697ac-a881-53ca-a8a0-92d86ca3da5b --path "$TARGET" --out "$TARGET/reports" -v` |
| `review … --explain …` | Review then deep-dive those UUIDs | `repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only --explain a08697ac-a881-53ca-a8a0-92d86ca3da5b` |
| `repolens pr-summary` | Critical/High suggested-fix Markdown | `repolens pr-summary "$TARGET/reports/gate_review_report_review_2026-08-06_1928.json"` |
| `… --github-summary` | Appends to `$GITHUB_STEP_SUMMARY` | `repolens pr-summary --github-summary` |
| `… --annotate` | `::error` / `::warning` for Actions | `repolens pr-summary --annotate` |
| `repolens score-report …` | Actionability metrics table | `repolens score-report "$TARGET/reports/gate_review_report_review_2026-08-06_1928.json"` |
| `… --json` | Same metrics as JSON | `repolens score-report "$TARGET/reports/….json" --json` |
| `repolens export …` | Echo/convert; `--pdf` if `pandoc` | `repolens export "$TARGET/reports/gate_review_report_review_2026-08-06_1928.md"` |
| `repolens feedback down <fingerprint>` | Appends `.repolens-ignore` (local) | `repolens feedback down a08697ac-a881-53ca-a8a0-92d86ca3da5b --reason false_positive --path "$TARGET"` |
| `repolens feedback list` | Lists active ignore entries | `repolens feedback list --path "$TARGET"` |

---

## 5) Project state & packs

| Command | Expect | Example |
|---------|--------|---------|
| `repolens adaptive status` | Fingerprint cache + recommended timeout | `repolens adaptive status --path "$TARGET"` |
| `repolens learn status` | Consent / index status (opt-in) | `repolens learn status --path "$TARGET"` |
| `repolens learn build` | Builds local index under `.repolens/` | `repolens learn build --path "$TARGET" --accept-local-learning` |
| `repolens learn clear` | Deletes index DB (consent kept) | `repolens learn clear --path "$TARGET"` |
| `repolens packs list` | Domain pack table (`azure-sentinel` today) | `repolens packs list` |

Packs are **off by default**. Enable with `--pack <id>` or `[packs] enabled = […]`.  
Pack-only smoke + if/then: [packs-quickcheck.md](./packs-quickcheck.md).

---

## 6) If you see this → it means

| Observation | Meaning | Next step / example |
|-------------|---------|---------------------|
| Summary all zeros after `--scanners-only` | Clean scanners (and packs if any) | Normal — e.g. `repolens review --path "$TARGET" --scanners-only` |
| `LLM bypassed (scanners clean…)` | Triage/`--ci` skipped the model on purpose | Expected; for narrative drop `--ci` or force pack: `repolens review --path "$TARGET" --full --deep --timeout 3600` |
| Many **Medium** findings but Slow Brain bypassed | Floor is **HIGH** — Medium heuristics do not wake LLM | Expected under `--ci`; see [Fast Brain vs Slow Brain](#fast-brain-vs-slow-brain-commands--examples) |
| Report under wrong repo’s `reports/` | Relative `--out reports` follows **shell cwd**, not `--path` | Always use `"$TARGET/reports"` (absolute) |
| `LLM pack: N/200` then bypass | Pack planned, then triage short-circuited | Cosmetic order; still correct |
| Gate confidence 75% / scanners-only | Heuristic confidence without LLM | Normal for `--scanners-only` |
| Exit code **1** with `--fail-on HIGH` | Finding at/above threshold (CI: usually **scanner** rows) | Open report; or `repolens feedback down <fingerprint> --reason false_positive --path "$TARGET"` |
| Exit code **2** / `ScannerRequirementError` | `--require-scanners` and a tool missing | `repolens plugins install all --yes` |
| `command not found: repolens` | Venv not activated / not installed | `source .venv/bin/activate` then `repolens version` |
| Unknown command (`packs`, `pr-summary`, …) | Old install | `pip install -e ".[dev]"` from latest clone |
| `Source error` / exit **3** | Clone or remote auth failed | Prefer local `--path`; else [remote-sources.md](./remote-sources.md) |
| Empty `--path` weirdness | Shell `TARGET = …` with spaces | `TARGET=/Users/you/proj` (no spaces around `=`) |
| No `Domain packs:` with `--pack` | Detail is verbose-only | Add `-v`: `… --pack azure-sentinel -v` |
| Ollama timeout / hung LLM | Model slow or not running | `ollama list`; `repolens review … --timeout 1800 -v` |
| `explain` cannot find UUID | Wrong report dir or stale Occurrence | Prefer **Fingerprint**; `repolens explain <fingerprint> --path "$TARGET" --out "$TARGET/reports"` after a JSON report exists |
| `No gate review JSON found` | `--path` / `--out` point at a different cwd/repo | `cd` to the reviewed repo, or pass absolute `--path` / `--out` (error lists dirs searched) |
| Suppressed findings still in Markdown | Listed under Suppressed; excluded from fail-on/SARIF | Intended — `repolens feedback list --path "$TARGET"` |

---

## Fast Brain vs Slow Brain (commands & examples)

RepoLens is a **Two-Lane** product. The CLI summary and Markdown report open with a **`Two-Lane:`** headline so you can see which lane ran.

| Lane | What it is | Default scope | Typical time |
|------|------------|---------------|--------------|
| **Fast Brain** | Deterministic heuristics (+ domain packs) | Matched tree up to **10k** files | **Seconds** |
| **Scanners** | gitleaks / Semgrep / OSV / … | **Full** tree | Seconds–minutes (warm) |
| **Slow Brain** | LLM narrative (`--deep` multi-pass by default) | Triage hits, adaptive pack, or forced full (≤ **200** by default) | **Minutes–hours** (local 32B) |

**Rule of thumb:** Fast Brain + scanners answer “what lights up quickly?” Slow Brain answers “explain and plan fixes on a prioritised slice.” They are not the same cost.

### Which command runs which lane?

Set once: `TARGET=/Users/[username]/Development/[your-project]`  
Always prefer **absolute** `--out "$TARGET/reports"` (relative `reports` follows the shell cwd, not `--path`).

| Goal | Flags | Fast Brain | Slow Brain | Expect |
|------|-------|------------|------------|--------|
| Inventory only | `--dry-run` | no | no | Tree/stats only |
| Fast lane only (no LLM) | `--scanners-only` | yes | no | Heuristics + scanners in seconds |
| **Fair PR / CI Two-Lane** | `--ci --deep --fail-on HIGH` | yes | only if hits ≥ floor | Often **`Slow Brain: bypassed (triage clean)`** in ~1s when scanners (and heuristic hits at floor) are clean |
| Adaptive deep (no force) | `--deep` (omit `--full`) | yes | adaptive pack | Warm runs may still take a full pack — check headline |
| Force full Slow Brain | `--full --deep` | yes | full LLM pack (≤200) | Often **≥1 h** on local 32B — audit, not a speed demo |
| Changed files only | `--changed` (+ optional `--deep`) | yes | added/changed only | Empty pack if nothing changed |
| Thin LLM | `--no-deep` | yes | single-shot sample | Faster, thinner coverage |

### Copy-paste recipes

```bash
TARGET=/Users/[username]/Development/[your-project]

# 1) Fast Brain + scanners only (seconds) — CQ / hygiene signal without LLM
repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only -v

# 2) Fair Two-Lane / PR-style CI (preferred dogfood for *speed*)
repolens review --path "$TARGET" --out "$TARGET/reports" \
  --ci --deep --fail-on HIGH --verbose --timeout 3600

# 3) Adaptive deep without forcing full pack (LLM may still run a large pack)
repolens review --path "$TARGET" --out "$TARGET/reports" \
  --deep --verbose --timeout 3600

# 4) Forced full Slow Brain (release / quality audit — budget an hour+ on local 32B)
repolens review --path "$TARGET" --out "$TARGET/reports" \
  --full --deep --verbose --timeout 3600 --model qwen2.5-coder:32b
```

### Reading the headline (real-shaped examples)

| You ran | Typical `Two-Lane:` / progress | Meaning |
|---------|--------------------------------|---------|
| `--ci --deep` on a clean tree | `Fast Brain: 184 file(s) in 0.1s · Slow Brain: bypassed (triage clean)` · `LLM pack: 0/…` | Correct CI behaviour — **not** a bug |
| `--ci` with only **Medium** heuristics | Same bypass; report still lists Medium/Low Fast Brain rows | Default severity floor is **HIGH** — Medium does **not** wake Slow Brain |
| `--ci` with High/Critical scanner (or floor) hits | `Slow Brain: N file(s)…` · LLM pack = hit files | Expensive lane only where triage pointed |
| `--full --deep` | `LLM pack: 184/184` (or up to max_files) · long wait | You asked for the full Slow Brain sample |

**“Triage clean”** means *clean at the severity floor* (default **HIGH**), not *zero findings*. Fast Brain can still report dozens of Medium nesting / mega-file / hygiene issues while Slow Brain stays off.

### Fair dogfood (PatternSorcerer-class)

Use **recipe 2** (`--ci --deep`) when comparing speed or PR cost to other tools. Use **recipe 4** (`--full --deep`) only when you intentionally want a forced Slow Brain pack for quality. Do **not** use `--full` to “show off” Two-Lane speed.

More context: [faq.md — fair dogfood](./faq.md#what-is-a-fair-dogfood-recipe-for-two-lane-speed) · [Two-Lane inventory](./faq.md#how-does-the-200-file-inventory-cap-work-are-the-other-files-at-risk) · [gitignore vs scanners](./faq.md#do-scanners-catch-missing-gitignore-rules) · [ci.md](./ci.md).

---

## 7) Approximate duration

**Split the clock:** inventory + scanners are usually **seconds**; a full local **deep LLM** review is often **hours**, even on a high-end Mac. RAM/CPU headroom helps, but Ollama prompt eval + multi-pass generation dominate.

### Dogfood anchors (local Ollama, deep on by default)

Measured on an **Apple M4 Pro / 128 GB** class machine (not a guarantee for your model/repo):

| Inventory size | Full `review` / `sentinel` (deep, local model) | Notes |
|----------------|------------------------------------------------|--------|
| ~200+ reviewable files | often **~1 hour or more** | Multi-pass deep; long “waiting for first token” is normal |
| ~800+ reviewable files | often **~2–3+ hours** | Worse with larger models / fuller packs |
| Same trees, `--scanners-only` | typically **~1–15 s** warm | Pack heuristics add negligible time |

Smaller packs (`--ci` bypass, `--changed`, `--no-deep`) cut LLM time a lot; they do **not** make a full-repo deep pass “a few minutes.”

### By workload (order-of-magnitude)

| Workload | High-end Apple Silicon (e.g. M4 Pro) | Mid Win/Linux laptop | Small CI (2 vCPU) |
|----------|--------------------------------------|----------------------|-------------------|
| `version` / `packs list` / `feedback list` | &lt;1 s | &lt;1 s | &lt;1 s |
| `plugins install all` (first time) | ~1–5 min | ~2–10 min | ~2–10 min |
| `--dry-run` | ~1–5 s | ~1–10 s | ~2–15 s |
| `--scanners-only` (± `--pack`) | ~1–15 s (warm) | ~5–60 s | ~15 s–few min |
| `--ci` **clean** → LLM bypass | ≈ scanners-only | ≈ scanners-only | ≈ scanners-only |
| `--ci` **with scanner hits** (small LLM pack) | often **tens of minutes** | often **tens of minutes–1+ h** | prefer scanners-only / cloud |
| Full deep + **Ollama** (~200 files) | often **≥1 h** | often **1–3+ h** | not for every PR |
| Full deep + **Ollama** (~800 files) | often **~2–3+ h** | often **several hours** | use scheduled audit only |
| Full deep + **cloud** API | still **many minutes–1+ h** (tokens/passes) | similar | cost/latency — prefer `--ci` |
| `explain` one UUID | often **minutes** (model-bound) | similar | similar |
| `pr-summary` / `score-report` / `export` | &lt;2 s | &lt;2 s | &lt;5 s |

**Why LLM feels “stuck”:** local models spend a long time on **prompt evaluation** before the first token; deep mode runs **several** large passes. Heartbeats (`-v`, default `--heartbeat 15`) show progress — see [faq.md](./faq.md).

**For PR CI:** use `--ci` / scanners-only so clean diffs finish in seconds–minutes. Reserve full deep for overnight or release audits.

---

## 8) Troubleshooting

Work top-down. Most “broken” first runs are install, PATH, or provider setup.

### A. CLI not found or wrong version

1. `which repolens` / `Get-Command repolens` — is it your `.venv`?
2. `repolens version` — matches the clone you expect?
3. From clone: `source .venv/bin/activate` then `pip install -e ".[dev]"`.
4. Still wrong? `hash -r` (bash) or open a new shell.

### B. Init / model / “nothing happens” on full review

1. Confirm you need LLM: for gates only, use `--scanners-only` or `--ci`.
2. `repolens init --provider ollama` (or cloud) — config must exist.
3. Ollama: `ollama list` and `curl -s localhost:11434/api/tags` — daemon up?
4. Cloud: env var set in **this** shell (`echo $OPENAI_API_KEY` non-empty)?
5. Raise wait: `--timeout 1800` or `REPOLENS_TIMEOUT=1800`.
6. See heartbeats: drop `-q`; use `-v`; `--heartbeat 15` (default).

### C. Scanners missing or always skipped

1. `repolens plugins status` — which tools are missing?
2. `repolens plugins install all --yes` then re-check status.
3. `--scanners off` explicitly disables — omit it for `auto`.
4. `--require-scanners` turns soft-skip into exit **2** — install or drop the flag.
5. SBOM/licenses need **Trivy** installed and enabled — [scanners.md](./scanners.md).

### D. CI / `--fail-on` surprises

1. Read the Markdown **and** JSON under `reports/` (or Action artifact).
2. With `--ci`, fail-on prefers **scanner** findings — LLM-only rows usually do not sole-fail.
3. Suppress noise with `.repolens-ignore` / `repolens feedback down` — [rules.md](./rules.md).
4. Action recipe: [ci.md](./ci.md).

### E. Remotes / clone failures

1. Exit **3** → auth or network on clone.
2. GitHub: `GITHUB_TOKEN` / `GH_TOKEN` or `gh auth token`.
3. Bitbucket / HF: see [remote-sources.md](./remote-sources.md).
4. Prefer local `--path` when the repo is already on disk.

### F. Packs / explain / feedback

1. Packs: `repolens packs list` → `--pack azure-sentinel -v` — [packs-quickcheck.md](./packs-quickcheck.md).
2. Explain: copy **Fingerprint** (`stableId` in JSON); **Occurrence** (`runId`) also works. Pass `--path` / `--out` if needed.
3. Feedback: `feedback down <fingerprint>` only writes local ignore — nothing uploads.

### G. Still stuck

1. Re-run with `-v` and note the last `→` phase line.
2. Check [faq.md](./faq.md) and [SUPPORT.md](./SUPPORT.md).
3. Open a bug with: OS, `repolens version`, exact command, last phase lines (redact secrets).
