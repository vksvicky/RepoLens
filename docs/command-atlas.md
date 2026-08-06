# RepoLens command atlas (holy grail)

One place for **install → run this → expect that → if odd, fix it**, with rough timings.
Deep guides stay linked; this page is the map.

| Need | Go here |
|------|---------|
| Paths / OS install detail | [try-on-your-repo.md](./try-on-your-repo.md) |
| Cloud vs Ollama vs scanners-only | [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) |
| Scanner plugins | [scanners.md](./scanners.md) |
| CI / GitHub Action | [ci.md](./ci.md) |
| Domain packs detail | [packs.md](./packs.md) · [packs-quickcheck.md](./packs-quickcheck.md) |
| Suppressions / rules | [rules.md](./rules.md) |
| FAQ | [faq.md](./faq.md) |

**How to read this page**

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

| Command | Expect |
|---------|--------|
| `repolens version` | Version string (e.g. `0.1.0a1`) |
| `repolens --help` | Command list including `review`, `sentinel`, `plugins`, `packs`, … |

### Configure once (only if you want LLM narrative)

| Goal | Command | Expect |
|------|---------|--------|
| Local Ollama | `repolens init --provider ollama` (or `--model qwen2.5:7b --force`) | Writes `~/.config/repolens/config.toml` |
| Cloud BYOK | `repolens init --provider openai` (or `anthropic` / `deepseek`) + set the API key env var | Same config file; key stays in env, not in git |
| Scanners / dry-run only | Skip `init` | `--scanners-only` / `--dry-run` need no model |

### Install scanner plugins (once per machine)

| Command | Expect |
|---------|--------|
| `repolens plugins install all --yes` | Downloads pinned tools under `~/.cache/repolens/tools/` (consent with `--yes` in CI) |
| `repolens plugins status` | Table: tool → available / missing |

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

| Command | Expect |
|---------|--------|
| `repolens version` | Prints version |
| `repolens init --provider ollama \| openai \| …` | Creates/updates user config (`--force` to overwrite) |
| `repolens plugins status` / `list` | Availability table |
| `repolens plugins install [all\|gitleaks\|…]` | Install messages; re-run `status` |

---

## 3) Review family

`review` = full P1→P2→P3 · `sentinel` = security P1 · `architecture` = architecture / readiness.  
Shared flags unless noted (`--full-audit` is mainly on `review`).

### Recipes → what you should see

| Recipe | Expect |
|--------|--------|
| `repolens review --path "$TARGET" --dry-run` | Inventory only; report notes dry-run; **no** scanners/LLM |
| `… --scanners-only` | Scanners run; summary table; Markdown/JSON under `--out` / `reports/` |
| `… --scanners-only -v` | Extra `·` detail (per-scanner status, SBOM path, packs line if enabled) |
| `… --ci --fail-on HIGH` | Triage routing; often **`LLM bypassed (scanners clean at triage floor)`** when scanners clean |
| `…` (full LLM, after `init`) | Inventory → scanners → LLM wait/heartbeats → report; deep multi-pass **on** by default |
| `… --no-deep` | Single-shot LLM (faster, thinner coverage) |
| `… --changed` / `--full` | Smaller or forced-full LLM pack (adaptive) |
| `… --pack azure-sentinel -v` | `Domain packs: azure-sentinel (N heuristic finding(s))` |
| `… --sarif` | Also writes anchored SARIF under reports |
| `… --verify-findings` | Critical location re-check notes (non-fatal); no-op if no Criticals |
| `repolens sentinel --path "$TARGET"` | Security-focused report (does not overwrite a full `review` report name pattern the same way — check `reports/`) |
| `repolens architecture --path "$TARGET"` | Architecture playbook path |

### Review progress lines (common)

| Line | Meaning |
|------|---------|
| `Fast brain inventory: K of N matched…` | Lane 1 file set for heuristics (default cap 10k) |
| `Slow brain LLM pool: top 200…` | Lane 2 sample (when Fast &gt; LLM cap) |
| `Fast brain: heuristics on K file(s)…` | Parallel deterministic lane |
| `… dropped from inventory pack` | Still on disk; fell out of fingerprint/LLM view |
| `… removed from tree` | Path gone / not a file anymore |
| `Scanners: finished (K finding(s), X/Y ran)` | Deterministic tools done |
| `LLM bypassed (scanners clean…)` | `--ci` / triage: no LLM spend |
| `LLM pack: A/B file(s)` | Adaptive / triage file selection |
| `Domain packs: …` | Pack heuristics ran (`-v` detail) |
| `Writing report → …` | Artifacts landing |
| Summary table Critical/High/… | Severity counts for this run |

---

## 4) After a report

| Command | Expect |
|---------|--------|
| `repolens explain <runId\|stableId> --path "$TARGET"` | Writes `reports/explain_*.md` (diagram best-effort; rarely fails the command) |
| `repolens review … --explain uuid[,uuid]` | Review then explain those IDs |
| `repolens pr-summary` / `… reports/foo.json` | Markdown of Critical/High suggested fixes |
| `repolens pr-summary --github-summary` | Appends to `$GITHUB_STEP_SUMMARY` when set |
| `repolens pr-summary --annotate` | Prints `::error` / `::warning` for Actions |
| `repolens score-report reports/gate_….json` | Actionability metrics table (not remediation rate/MTTR) |
| `repolens score-report … --json` | Same metrics as JSON |
| `repolens export reports/gate_….md` | Echo/convert; `--pdf` if `pandoc` available |
| `repolens feedback down <stableId> --reason "…"` | Appends `.repolens-ignore` (local only) |
| `repolens feedback list` | Lists active ignore entries |

---

## 5) Project state & packs

| Command | Expect |
|---------|--------|
| `repolens adaptive status --path "$TARGET"` | Fingerprint cache stats + recommended timeout |
| `repolens learn status --path "$TARGET"` | Consent / index status (opt-in) |
| `repolens learn build --path "$TARGET" --accept-local-learning` | Builds local index under `.repolens/` |
| `repolens learn clear --path "$TARGET"` | Deletes index DB (consent kept) |
| `repolens packs list` | Domain pack table (`azure-sentinel` today) |

Packs are **off by default**. Enable with `--pack <id>` or `[packs] enabled = […]`.  
Pack-only smoke + if/then: [packs-quickcheck.md](./packs-quickcheck.md).

---

## 6) If you see this → it means

| Observation | Meaning | Next step |
|-------------|---------|-----------|
| Summary all zeros after `--scanners-only` | Clean scanners (and packs if any) | Normal for a tidy repo |
| `LLM bypassed (scanners clean…)` | Triage/`--ci` skipped the model on purpose | Expected; use full review without `--ci` for narrative |
| `LLM pack: N/200` then bypass | Pack planned, then triage short-circuited | Cosmetic order; still correct |
| Gate confidence 75% / scanners-only | Heuristic confidence without LLM | Normal for `--scanners-only` |
| Exit code **1** with `--fail-on HIGH` | Finding at/above threshold (in CI: usually **scanner** rows) | Open report; fix or suppress ([rules.md](./rules.md)) |
| Exit code **2** / `ScannerRequirementError` | `--require-scanners` and a tool missing | `repolens plugins install …` |
| `command not found: repolens` | Venv not activated / not installed | Activate `.venv` or reinstall editable |
| Unknown command (`packs`, `pr-summary`, …) | Old install | `pip install -e ".[dev]"` from latest clone |
| `Source error` / exit **3** | Clone or remote auth failed | Check token env / `gh auth` — [remote-sources.md](./remote-sources.md) |
| Empty `--path` weirdness | Shell `set TARGET = …` mistake | Assign `TARGET=/path` with no spaces — [try-on-your-repo.md](./try-on-your-repo.md) |
| No `Domain packs:` with `--pack` | Detail is verbose-only | Add `-v` |
| Ollama timeout / hung LLM | Model slow or not running | `ollama list` / raise `--timeout`; see setup guide |
| `explain` cannot find UUID | Wrong report dir or stale ID | Pass `--out` / run after a JSON report exists |
| Suppressed findings still in Markdown | Listed under Suppressed; excluded from fail-on/SARIF | Intended |

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
2. Explain: copy `runId` or `stableId` from the latest JSON; pass `--path` / `--out` if reports are not under `./reports`.
3. Feedback: `feedback down` only writes local ignore — nothing uploads.

### G. Still stuck

1. Re-run with `-v` and note the last `→` phase line.
2. Check [faq.md](./faq.md) and [SUPPORT.md](./SUPPORT.md).
3. Open a bug with: OS, `repolens version`, exact command, last phase lines (redact secrets).
