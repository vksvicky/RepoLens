# Try RepoLens on your code

Use these steps to review a project **on disk** or from **GitHub / Bitbucket / Hugging Face / any git URL** before relying on PyPI or CI.

Replace placeholders in the commands:

| Placeholder | Meaning | Example substitution |
|-------------|---------|----------------------|
| `[username]` | Your OS user name | `jackfrost` |
| `[your-project]` | Folder name of the repo to review | `acme-api` |
| `[owner]` / `[repo]` | GitHub owner and repo | `jackfrost` / `acme-api` |
| `[workspace]` / `[repo]` | Bitbucket workspace and repo | `jackfrost` / `acme-api` |
| `[org]` / `[name]` | Hugging Face org and model/dataset/space | `jackfrost` / `acme-model` |

So if your user is `jackfrost` and the project is `acme-api`, then on macOS  
`/Users/[username]/Development/[your-project]` → `/Users/jackfrost/Development/acme-api`.  
Do **not** leave the brackets in the path you type.

**Prerequisites (all platforms):** [Git](https://git-scm.com/downloads) and **Python 3.11+** (`python3 --version` / `py -3.11 --version`).

### What does `pip install -e ".[dev]"` mean?

These extras configure **how you install RepoLens**, not the project under review. Full package lists and “where this lives”: **[install-extras.md](./install-extras.md)**.

| Part | Meaning |
|------|---------|
| `pip install` | Install a Python package into the active virtualenv |
| `-e` | **Editable** install — you run code from this clone; edits apply without reinstalling |
| `.` | Install the package in the **current directory** (the RepoLens repo root that contains `pyproject.toml`) |
| `[dev]` | Also install RepoLens’s optional **`dev`** extra (pytest, ruff, mypy, …) |

For day-to-day dogfood from a clone, use `".[dev]"`. Add Semgrep with `".[dev,scanners]"` if you want it via pip.

---


## 1) Install RepoLens from a clone

### macOS

```bash
cd /Users/[username]/Development/RepoLens
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
repolens version
```

Example after substitution: `cd /Users/jackfrost/Development/RepoLens`

### Linux

```bash
cd /home/[username]/Development/RepoLens
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
repolens version
```

Example after substitution: `cd /home/jackfrost/Development/RepoLens`

If `python3` is missing, install via your distro (for example `sudo apt install python3 python3-venv python3-pip` on Debian/Ubuntu).

### Windows (PowerShell)

Prefer **PowerShell**; Git Bash also works with Unix-style activate.

```powershell
cd C:\Users\[username]\Development\RepoLens
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
repolens version
```

Example after substitution: `cd C:\Users\jackfrost\Development\RepoLens`

If script activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Or activate with cmd.exe: `.venv\Scripts\activate.bat`.

---

## 2) Point `--path` at the repo to review

Keep the RepoLens venv **activated**, then set a target path for your OS.

### macOS / Linux shell note

Assign the path **without** `set` and **without** spaces around `=`:

```bash
# Correct (bash / zsh):
TARGET=/Users/[username]/Development/[your-project]

# Wrong — does not set TARGET the way these docs expect:
# set TARGET = /Users/...
```

### macOS

```bash
TARGET=/Users/[username]/Development/[your-project]
```

Example: `TARGET=/Users/jackfrost/Development/acme-api`

### Linux

```bash
TARGET=/home/[username]/Development/[your-project]
```

Example: `TARGET=/home/jackfrost/Development/acme-api`

### Windows (PowerShell)

```powershell
$TARGET = "C:\Users\[username]\Development\[your-project]"
```

Example: `$TARGET = "C:\Users\jackfrost\Development\acme-api"`

### One-time: configure a model provider (full LLM review only)

Ollama (or a cloud key) must be wired into RepoLens once. Having Ollama installed is **not** enough.

```bash
ollama list                                          # see installed models
repolens init --provider ollama                      # picks an installed model (e.g. qwen2.5:7b)
# or pin one:  repolens init --provider ollama --model qwen2.5:7b --force
```

Writes `~/.config/repolens/config.toml` (or `$XDG_CONFIG_HOME/repolens/config.toml`).  
Skip this if you only use `--dry-run` / `--scanners-only`. Details: [setup-ai-and-scanners.md](./setup-ai-and-scanners.md#option-b--local-ai-on-your-computer-eg-ollama).

### Run the review

**macOS / Linux** (bash/zsh):

```bash
# Inventory only (no LLM, no scanners)
repolens review --path "$TARGET" --out "$TARGET/reports" --dry-run

# Optional: install scanners once on this machine (macOS + Linux; see note below)
repolens plugins install all --yes
repolens plugins status

# Deterministic scanners only (no API key required)
repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only --fail-on ""

# Full review (after init above)
# Progress: phase lines by default; -v for detail; heartbeats every 15s during LLM;
#           --heartbeat 0 to disable heartbeats; -q for quiet (CI)
# Deep coverage (heuristics + chunked passes) is on by default; --no-deep = single-shot
repolens review --path "$TARGET" --out "$TARGET/reports" --verbose
# After the first run: inspect adaptive cache / recommended timeout
repolens adaptive status --path "$TARGET"
# Warm / PR-sized re-run (smaller pack; may skip LLM if nothing changed)
# repolens review --path "$TARGET" --out "$TARGET/reports" --changed --verbose
# Large / audit-style: --full-audit (uses deep + full architecture checklist)
# repolens review --path "$TARGET" --out "$TARGET/reports" --full-audit --verbose
# Security-only (P1): does not overwrite a review report; arch metrics omitted
repolens sentinel --path "$TARGET" --out "$TARGET/reports"
```

**Windows (PowerShell):**

```powershell
repolens review --path $TARGET --out "$TARGET\reports" --dry-run

# Scanners: see platform note below — dry-run and LLM review still work
repolens review --path $TARGET --out "$TARGET\reports"

repolens sentinel --path $TARGET --out "$TARGET\reports"
```

Open the Markdown under `$TARGET/reports/gate_review_report_{mode}_YYYY-MM-DD_HHMM.md` (for jackfrost’s sample: `acme-api/reports/…`).

---

## Guided review (interactive)

From a RepoLens checkout (with `repolens` on your `PATH`):

```bash
./scripts/repolens-guided.sh
# or: python3 scripts/repolens_guided.py
```

The wizard asks for path, security/architecture/both, scanners-only vs full LLM,
**deep coverage** (default **Y** for review / full-audit; emits `--deep` / `--no-deep`
when the CLI supports it), installed Ollama models, timeout, and other flags —
each option shows a short recommendation. It prints the exact command and asks
**Y/n** before running.

On large trees, keep deep **on** so checklist coverage and heuristics can surface
structural themes that a single-shot pass often misses.

---

## 3) Review a remote (GitHub, Bitbucket, Hugging Face, git URL)

Keep the RepoLens venv **activated**. Use **exactly one** source flag — do not combine `--path` with a remote flag.

Remote clones are temporary; reports land under **`./reports/` in your current working directory** (override with `--out`). Auth and edge cases: [remote-sources.md](./remote-sources.md).

### Local folder (same as §2)

```bash
repolens review --path /Users/[username]/Development/[your-project] --dry-run
# Example: repolens review --path /Users/jackfrost/Development/acme-api --dry-run
```

### GitHub (`--github`)

```bash
repolens review --github [owner]/[repo] --dry-run
repolens review --github [owner]/[repo] --ref main --scanners-only --fail-on ""
repolens review --github [owner]/[repo] --ref main
repolens sentinel --github [owner]/[repo]

# Example:
# repolens review --github jackfrost/acme-api --ref main --dry-run
```

Private repos: set `GITHUB_TOKEN` / `GH_TOKEN`, or run `gh auth login`.

### Any git URL (`--git-url`)

```bash
repolens review --git-url https://github.com/[owner]/[repo].git --ref main --dry-run
repolens review --git-url https://gitlab.com/[owner]/[repo].git --ref main --dry-run
repolens review --git-url git@github.com:[owner]/[repo].git --dry-run

# Example:
# repolens review --git-url https://github.com/jackfrost/acme-api.git --ref main --dry-run
```

### Bitbucket (`--bitbucket`)

```bash
repolens review --bitbucket [workspace]/[repo] --dry-run
repolens review --bitbucket [workspace]/[repo] --ref main --scanners-only --fail-on ""
repolens review --bitbucket [workspace]/[repo] --ref main

# Example:
# repolens review --bitbucket jackfrost/acme-api --ref main --dry-run
```

Private repos: set `BITBUCKET_TOKEN` (or `BITBUCKET_APP_PASSWORD`). For app passwords also set `BITBUCKET_USERNAME`.

### Hugging Face Hub (`--hf`)

```bash
# Model repo
repolens review --hf [org]/[name] --dry-run

# Dataset or Space (prefix required)
repolens review --hf datasets/[org]/[name] --dry-run
repolens review --hf spaces/[org]/[name] --dry-run

# Example:
# repolens review --hf jackfrost/acme-model --dry-run
# repolens review --hf datasets/jackfrost/acme-data --dry-run
```

Private Hub repos: set `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN`.

### Where reports go

| Source | Default report directory |
|--------|---------------------------|
| `--path …` | Inside that project’s `reports/` (or `--out`) |
| `--github` / `--bitbucket` / `--hf` / `--git-url` | `./reports/` under your **cwd** (or `--out DIR`) |

---

## 4) Review the RepoLens repo itself (dogfood)

### macOS

```bash
cd /Users/[username]/Development/RepoLens
source .venv/bin/activate

repolens review --path . --out ./reports-dogfood --dry-run
repolens plugins install all --yes
repolens review --path . --out ./reports-dogfood --scanners-only --fail-on ""
```

### Linux

```bash
cd /home/[username]/Development/RepoLens
source .venv/bin/activate

repolens review --path . --out ./reports-dogfood --dry-run
repolens plugins install all --yes
repolens review --path . --out ./reports-dogfood --scanners-only --fail-on ""
```

### Windows (PowerShell)

```powershell
cd C:\Users\[username]\Development\RepoLens
.\.venv\Scripts\Activate.ps1

repolens review --path . --out .\reports-dogfood --dry-run
# plugins install: not pinned for Windows yet — use dry-run / LLM, or install tools manually
repolens review --path . --out .\reports-dogfood
```

`reports-dogfood/` is gitignored. Pass criteria for a pre-publish check are in [publishing.md](./publishing.md#pre-publish-dogfood).

---

## Platform notes

| Topic | macOS | Linux | Windows |
|-------|-------|-------|---------|
| Venv activate | `source .venv/bin/activate` | same | `.\.venv\Scripts\Activate.ps1` |
| Typical home | `/Users/[username]` | `/home/[username]` | `C:\Users\[username]` |
| Example home | `/Users/jackfrost` | `/home/jackfrost` | `C:\Users\jackfrost` |
| `repolens plugins install` (gitleaks / osv) | Supported (arm64 + amd64) | Supported (amd64 + arm64) | **Not pinned yet** — install tools yourself or use WSL; see [scanners.md](./scanners.md) |
| Semgrep (`pip` / `repolens[scanners]`) | Yes | Yes | Usually yes via pip |
| Env vars for API keys | `export OPENAI_API_KEY=...` | same | `$env:OPENAI_API_KEY = "..."` — see [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) |
| Semgrep config override | `export REPOLENS_SEMGREP_CONFIG=./.semgrep.yml` | same | `$env:REPOLENS_SEMGREP_CONFIG = ".\.semgrep.yml"` |

**WSL tip:** On Windows, running under [WSL](https://learn.microsoft.com/windows/wsl/) uses the **Linux** steps (including `plugins install`).

---

## Tips

| Goal | Flag / note |
|------|-------------|
| Current directory | Omit `--path` or use `--path .` |
| No LLM key | Use `--dry-run` or `--scanners-only` (where scanners are available) |
| Deep coverage (default on) | `--deep` multi-pass + heuristics; `--no-deep` single-shot |
| Full architecture audit | `--full-audit` (pairs with deep) |
| Faster warm re-review | `--changed` or default `adaptive.mode=auto`; see `repolens adaptive status` |
| Force full LLM pack | `--full` |
| Cloud BYOK same pipeline | `repolens init --provider openai\|anthropic\|deepseek` (Phase A) |
| Fail CI-style on High+ | `--fail-on HIGH` |
| One source only | Exactly one of `--path`, `--github`, `--bitbucket`, `--hf`, `--git-url` |
| Remotes deep dive | [remote-sources.md](./remote-sources.md) |

Setup for AI providers: [setup-ai-and-scanners.md](./setup-ai-and-scanners.md).  
Scanners detail: [scanners.md](./scanners.md).  
CI Action: [ci.md](./ci.md).
