# Setup guide: three ways to run reviews

**Audience:** anyone setting up RepoLens for the first time.  
**Related:** [FAQ (plain English)](./faq.md#decisions-in-plain-english-start-here) · [Why these options exist](./design/ai-keys-scanners-and-local-learning.md#52-is-repolens-self-sufficient-out-of-the-box)

RepoLens itself is the **review process**. To actually run a review you pick **one** of these paths (you can combine 1 or 2 with 3 later):

| Option | Best when… | Full written report? |
|--------|------------|----------------------|
| **[A. Cloud AI key](#option-a--cloud-ai-your-own-api-key)** | You already use OpenAI / Anthropic / similar | Yes |
| **[B. Local AI](#option-b--local-ai-on-your-computer-e-g-ollama)** | You want code to stay on your machine | Yes |
| **[C. Scanners only](#option-c--checklist-scanners-only-no-ai-narrative)** | You only need secrets / CVE-style lists | No — inventory only |

> **Status today:** Phases **0–4** complete — install from source (`pip install -e .`) and run `repolens init`.  
> - Options **A** and **B** work via the CLI **or** **[playbooks + any LLM chat](./using-playbooks.md)**.  
> - Option **C** scanners: `repolens plugins install` · [scanners.md](./scanners.md).  
> - CI: [ci.md](./ci.md) · Local learning: [local-learning.md](./local-learning.md).  
> - Test on any local folder: [try-on-your-repo.md](./try-on-your-repo.md).  
> - Full command atlas: [command-atlas.md](./command-atlas.md).

---

## Before any option

1. Install **[Git](https://git-scm.com/downloads)** if you do not have it.  
2. Have the **project folder** on your computer, **or** use a remote (`--github` / `--git-url` — see [remote-sources.md](./remote-sources.md)).  
3. Decide how private the code is:
   - OK to send excerpts to a cloud AI provider → Option A is fine.  
   - Must stay on this machine → Option B (and skip cloud keys).

---

## Option A — Cloud AI (your own API key)

### What you are doing
You create an account with an AI company, copy a **secret key**, and let RepoLens (or your LLM chat tool) use that key to read your code and write the report.

### Steps

#### 1) Create a key with a provider

**First-class BYOK** (named in `repolens init --provider …`):

| Provider | Env var | Where to get a key (typical) | Progress while waiting |
|----------|---------|------------------------------|------------------------|
| `openai` | `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) → API keys | Streamed chars/chunks |
| `anthropic` | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API keys | Streamed chars/chunks (Messages SSE) |
| `deepseek` | `DEEPSEEK_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com) → API keys | Streamed chars/chunks |

**Escape hatch** — any OpenAI-compatible HTTP API (Azure OpenAI, Groq, Mistral, OpenRouter, LM Studio, vLLM, …):

```bash
repolens init --provider openai_compatible --model <name> \
  --base-url https://your-host/v1 --force
export REPOLENS_API_KEY="..."
```

| Provider | Env var | Notes |
|----------|---------|--------|
| `openai_compatible` | `REPOLENS_API_KEY` | Set `base_url` + `model` for that host; same streamed wait UX |

**Not BYOK:** `ollama` (local) and `none` (scanners / dry-run only).

**Coming later:** Phase 8 adds named aliases/recipes (Azure, Mistral, Groq, OpenRouter, …); Phase 9 adds native Gemini/Vertex/Bedrock when OpenAI-compatible is not enough. See [phases.md](./phases.md).

1. Sign up / sign in.  
2. Add billing if the provider requires it.  
3. Create an API key.  
4. **Copy it once** and store it in a password manager—you often cannot view it again.

Treat the key like a password. Do **not** paste it into Slack, GitHub, or a report file.

#### 2) Put the key on your computer (not in the project repo)

**macOS / Linux (current terminal session):**

```bash
export OPENAI_API_KEY="sk-your-key-here"          # OpenAI example
# export ANTHROPIC_API_KEY="..."                  # Anthropic
# export DEEPSEEK_API_KEY="..."                   # DeepSeek
```

To make it stick for new terminals, add the same line to your shell profile (`~/.zshrc` or `~/.bashrc`), or use your OS “secrets” / env management tool.

**Windows (PowerShell, current session):**

```powershell
$env:OPENAI_API_KEY = "sk-your-key-here"
```

#### 3) Tell RepoLens which provider to use *(CLI)*

Create or edit config (see [`.repolens.example.toml`](../.repolens.example.toml)), or run `repolens init`:

```toml
# ~/.config/repolens/config.toml  OR  ./.repolens.toml
[model]
provider = "openai"                 # openai | anthropic | deepseek | openai_compatible
model = "gpt-4.1"                   # use a model your account supports
api_key_env = "OPENAI_API_KEY"      # name of the env var — not the key itself
# base_url = "https://…"            # required for most openai_compatible hosts
```

Then:

```bash
repolens review --path /path/to/your/project
# or
repolens sentinel --path /path/to/your/project   # security-only
# Large repos / full audits: deep coverage is on by default
# repolens review --path /path/to/your/project --full-audit --deep
# Faster thin pass: --no-deep
```

All first-class BYOK providers and `openai_compatible` use the **same `--deep` pipeline** as Ollama—provider choice is a quality/cost/privacy multiplier, not a separate review path. Wait heartbeats show streamed output for all of them (Ollama adds `/api/ps` load detail).

#### 4) Optional — playbooks without the CLI

1. Open your **project** in an editor or LLM chat that can see the files.  
2. Follow [using-playbooks.md](./using-playbooks.md).  
3. Ask for a Markdown export if you need a saved report.

### Checklist — Option A

- [ ] Provider account created  
- [ ] API key stored safely (password manager)  
- [ ] Key set in environment variable (not committed to git)  
- [ ] Config points at provider (`repolens init`) or your LLM chat is signed in  
- [ ] You accept that **code excerpts** go to that provider during a review  

---

## Option B — Local AI on your computer (e.g. Ollama)

### What you are doing
You install a program that runs an AI model **on your machine**. RepoLens talks to that local program. No cloud API key is required for the AI chat.

### Steps

#### 1) Install Ollama

1. Open [https://ollama.com](https://ollama.com) and download for your OS.  
2. Install and open Ollama so it is running in the background.  
3. Confirm in a terminal:

```bash
ollama --version
```

#### 2) Download a model (one-time, needs network)

Pick a model that fits your machine (any model Ollama supports). Examples:

```bash
ollama pull qwen2.5:7b
# or: ollama pull llama3.1
ollama list   # confirm what is installed
```

Larger models need more RAM/disk. If pull fails, try a smaller model from Ollama’s library.

#### 3) Smoke-test the local model

```bash
ollama run qwen2.5:7b "Reply with the single word: pong"
# use the same name `ollama list` shows
```

You should get a short reply. Leave Ollama running.

#### 4) Point RepoLens at Ollama *(CLI)*

Installing Ollama alone is **not** enough. RepoLens does not assume a provider until you write config once:

```bash
repolens init --provider ollama
# Writes ~/.config/repolens/config.toml  (or $XDG_CONFIG_HOME/repolens/config.toml)
# Uses the first model from `ollama list` when --model is omitted
```

To pin a specific installed model:

```bash
repolens init --provider ollama --model qwen2.5:7b --force
```

That creates something like:

```toml
# ~/.config/repolens/config.toml
[model]
provider = "ollama"
model = "qwen2.5:7b"   # whatever init selected / you passed
base_url = "http://127.0.0.1:11434/v1"
# No cloud api_key_env needed
```

If you skip this step, `repolens review` errors with “No model provider configured” and (when Ollama is running) lists installed models and suggests `init`.

`init` also sets `timeout_seconds = 900` for Ollama (local models are slower than cloud APIs). Override with `--timeout`, `REPOLENS_TIMEOUT`, or edit the config.

#### 5) Run a review

```bash
repolens review --path /path/to/your/project --verbose
# Large repos: deep coverage (default) + more time, or narrow scope
# repolens review --path /path/to/your/project --full-audit --timeout 3600
# repolens review --path /path/to/your/project --mode diff --since HEAD~20
# Warm / PR-sized: --changed (skip LLM if no fingerprint delta)
# Force full pack: --full
# Thin single-shot: --no-deep
repolens adaptive status --path /path/to/your/project
```

Deep mode loads **rules by id** from the packaged registry (overridable under `.repolens/rules/`), not fixed author-machine Markdown paths. FAQ: [What is deep coverage?](./faq.md#what-is-deep-coverage).

**Adaptive cache (Phase 5):** After the first review, `.repolens/repolens.sqlite` stores fingerprints + run timings. Later `auto` runs send a smaller LLM pack. Inspect with `repolens adaptive status`. Timeout order: `--timeout` → `REPOLENS_TIMEOUT` → `[model].timeout_seconds` → recommended → provider default. Disable with `[adaptive] enabled = false`. FAQ: [What is the adaptive cache?](./faq.md#what-is-the-adaptive-cache-phase-5).

**Cloud BYOK (Phase A):** `openai` / `anthropic` / `deepseek` / `openai_compatible` use the same `--deep` pipeline as Ollama — switch with `repolens init --provider …`. Streaming wait progress works for all of them.

If you see **timed out**, the model did not finish within the HTTP limit — raise `--timeout`, use `--changed` / `--mode diff`, or run `--scanners-only` / `--dry-run` first.

Playbooks-only path still works: [using-playbooks.md](./using-playbooks.md).

### Checklist — Option B

- [ ] Ollama installed and running  
- [ ] Model pulled (`ollama pull …`)  
- [ ] Test prompt works  
- [ ] RepoLens config uses `provider = "ollama"` **(CLI)**  
- [ ] No cloud API key set (if you want a fully local path)  

### Tips

- First model download can be several GB.  
- Reviews may be slower than cloud AI on small laptops.  
- For “nothing leaves my machine,” do **not** also configure a cloud key.

---

## Option C — Checklist scanners only (no AI narrative)

### What you are doing
You install optional **security checklist tools**. They report things like leaked secrets or known-bad library versions. They do **not** write the full “here’s why and how to fix it” story—that still needs Option A or B.

### Steps

#### 1) Install Git (required)

Same as [Before any option](#before-any-option).

#### 2) Install the checklist tools you care about

Easiest with RepoLens (prompts for consent; use `--yes` in CI):

```bash
repolens plugins status
repolens plugins install all
# or: pip install -e ".[scanners]"   # Semgrep via pip; still run plugins install for gitleaks/osv
```

Or install tools yourself (any subset):

| Tool | Role | Typical install docs |
|------|------|----------------------|
| [gitleaks](https://github.com/gitleaks/gitleaks) | Find secrets in files | Project README / package managers |
| [Semgrep](https://semgrep.dev) | Pattern / SAST rules | `pip install semgrep` or their installer |
| [OSV-Scanner](https://google.github.io/osv-scanner/) | Known dependency vulnerabilities (CVE-related) | Their install guide |

Verify:

```bash
repolens plugins status
# or:
gitleaks version && semgrep --version && osv-scanner --version
```

#### 3) Enable scanners in RepoLens

```toml
[scanners]
enabled = ["gitleaks", "semgrep", "osv"]
require = false    # set true only if you want RepoLens to fail when a tool is missing
```

```bash
repolens review --path /path/to/your/project --scanners-only   # no AI story
# or combine with AI (scanners auto when present):
repolens review --path /path/to/your/project --scanners auto
```

Full flag reference: [scanners.md](./scanners.md).

### Checklist — Option C

- [ ] Git installed  
- [ ] At least one scanner available (`repolens plugins status`)  
- [ ] You understand this path does **not** replace the written AI report  
- [ ] Config lists enabled scanners (optional)  

---

## Combining options

| Combination | Result |
|-------------|--------|
| **A + C** | Cloud AI report + automated secret/CVE/SAST section |
| **B + C** | Local AI report + local scanners (strong privacy posture) |
| **A or B only** | Full narrative review; no automated CVE list until you add C |
| **C only** | Inventories and rule hits; no architecture/security narrative |

---

## Quick “which option?” flow

```text
Need a full written review with fix examples?
├─ Yes, and cloud is OK → Option A
├─ Yes, and keep AI on this PC → Option B
└─ No, only lists of secrets / known vulns → Option C

Want both understanding and inventories? → (A or B) + C
```

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| “No provider configured” **(CLI)** | Set Option A env key + config, or Option B Ollama config |
| Cloud key rejected | Regenerate key; check billing; confirm env var name matches `api_key_env` |
| Ollama connection refused | Start the Ollama app; confirm `ollama run …` works; check `base_url` port `11434` |
| Model too slow / out of memory | Pull a smaller model; close other apps |
| Scanner not found **(CLI)** | Install the binary or set `require = false` |
| Key accidentally committed | **Rotate/revoke** the key at the provider immediately; remove from git history |

---

## See also

- [using-playbooks.md](./using-playbooks.md) — reviews **today** without the CLI  
- [faq.md](./faq.md) — short answers  
- [design/ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md) — product decisions  
- [`.repolens.example.toml`](../.repolens.example.toml) — config template  
