# Setup guide: three ways to run reviews

**Audience:** anyone setting up RepoLens for the first time.  
**Related:** [FAQ (plain English)](./faq.md#decisions-in-plain-english-start-here) · [Why these options exist](./design/ai-keys-scanners-and-local-learning.md#52-is-repolens-self-sufficient-out-of-the-box)

RepoLens itself is the **review process**. To actually run a review you pick **one** of these paths (you can combine 1 or 2 with 3 later):

| Option | Best when… | Full written report? |
|--------|------------|----------------------|
| **[A. Cloud AI key](#option-a--cloud-ai-your-own-api-key)** | You already use OpenAI / Anthropic / similar | Yes |
| **[B. Local AI](#option-b--local-ai-on-your-computer-e-g-ollama)** | You want code to stay on your machine | Yes |
| **[C. Scanners only](#option-c--checklist-scanners-only-no-ai-narrative)** | You only need secrets / CVE-style lists | No — inventory only |

> **Status today:** Phases 1–3 — install from source (`pip install -e .`) and run `repolens init`.  
> - Options **A** and **B** work via the CLI **or** **[playbooks + any LLM chat](./using-playbooks.md)**.  
> - Option **C** scanners: `repolens plugins install` · see [scanners.md](./scanners.md).

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
Pick one (examples):

| Provider | Where to get a key (typical) |
|----------|------------------------------|
| OpenAI | [platform.openai.com](https://platform.openai.com) → API keys |
| Anthropic | [console.anthropic.com](https://console.anthropic.com) → API keys |
| DeepSeek | [platform.deepseek.com](https://platform.deepseek.com) → API keys |

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
provider = "openai"                 # or anthropic | deepseek | ...
model = "gpt-4.1"                   # use a model your account supports
api_key_env = "OPENAI_API_KEY"      # name of the env var — not the key itself
```

Then:

```bash
repolens review --path /path/to/your/project
# or
repolens sentinel --path /path/to/your/project   # security-only
```

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

Pick a model that fits your machine. Example:

```bash
ollama pull llama3.1
```

Larger models need more RAM/disk. If pull fails, try a smaller model from Ollama’s library.

#### 3) Smoke-test the local model

```bash
ollama run llama3.1 "Reply with the single word: pong"
```

You should get a short reply. Leave Ollama running.

#### 4) Point RepoLens at Ollama *(CLI)*

```toml
# ~/.config/repolens/config.toml
[model]
provider = "ollama"
model = "llama3.1"
base_url = "http://127.0.0.1:11434"
# No cloud api_key_env needed
```

```bash
repolens review --path /path/to/your/project
```

#### 5) Run a review

```bash
repolens init --provider ollama
repolens review --path /path/to/your/project
```

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
