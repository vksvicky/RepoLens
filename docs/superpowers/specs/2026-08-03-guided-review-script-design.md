# Guided review script (interactive CLI helper)

**Status:** Design approved (Approach 1; Bash launcher + Python wizard; confirm-then-run; local-first + advanced remotes)  
**Date:** 2026-08-03
**Depends on:** Existing `repolens review|sentinel|architecture` CLI flags; local Ollama optional

## 1. Problem

Users learning RepoLens face a long flag surface (`--scanners-only`, `--full`, `--full-audit`, `--timeout`, `--model`, mode commands). Cold LLM runs on ~200 files with a 7B Ollama model take many minutes. A guided helper should collect choices with **inline recommendations** and produce a correct `repolens` invocation before committing time to the model.

## 2. Decisions (locked)

| Decision | Choice |
|----------|--------|
| Delivery | Standalone scripts under `scripts/` — **not** a Typer subcommand (v1) |
| Platforms | Bash launcher + Python wizard (**A + C**); no PowerShell twin in v1 |
| Relationship | Python owns UX; Bash only `exec`s the Python file |
| After choices | Print command + tip → **Y/n** confirm → run; forward exit code |
| Sources | Local path first; remotes as an **advanced** branch in the same wizard |
| Dependencies | Stdlib-only Python; require `repolens` on `PATH`; do not import `repolens` package |
| Config writes | Wizard does **not** write `config.toml`; may suggest `repolens init` |

## 3. Files

| Path | Role |
|------|------|
| `scripts/repolens_guided.py` | Interactive wizard + pure helpers for argv / model parsing |
| `scripts/repolens-guided.sh` | Thin launcher: prefer `python3`, else `python`; `exec` the `.py` |
| `docs/try-on-your-repo.md` | Short “Guided review” subsection |
| `README.md` | One-line pointer to the script |
| `tests/test_guided_script.py` | Unit tests for helpers (no Ollama / no real review) |

## 4. Prompt flow

Numbered menus; each option includes a short recommendation on the same line (or immediately beside the choice).

1. **Source**
   - Local path (default) — path default `.`; out default `<path>/reports`
   - Advanced remote — GitHub / git URL / Bitbucket / HF + optional `--ref`
2. **Review kind**
   - Security only → `repolens sentinel` *(fastest LLM playbook)*
   - Architecture only → `repolens architecture`
   - Both → `repolens review` *(recommended default)*
3. **LLM depth**
   - Scanners only → `--scanners-only` *(no LLM; seconds)*
   - Dry-run inventory → `--dry-run`
   - Adaptive LLM (default) — omit `--full` *(warm runs smaller pack)*
   - Force full LLM pack → `--full` *(first deep audit / cold cache)*
4. **Playbook depth** (only when command is `review` and LLM will run)
   - Scoped architecture (default)
   - Full architecture audit → `--full-audit`
5. **Model** (only when LLM will run)
   - List installed Ollama models + “use config default”
   - Tip: smaller models faster but weaker schema adherence; 7B+ better for JSON
6. **Extras** (Y/n or short menu)
   - `--verbose` *(recommended)*
   - `--timeout` with suggestion (900 Ollama default; 1800 for large/first run)
   - `--format` md | json | both
   - `--scanners` auto | off
   - `--fail-on` none | HIGH | CRITICAL
7. **Summary** — display argv as a shell-safe command string + ETA tip → confirm → execute

Skip steps that do not apply (e.g. model / playbook depth when `--scanners-only` or `--dry-run`).

## 5. Ollama model discovery

Order:

1. `ollama list` (parse `NAME` column / first token per data row)
2. Else `GET http://127.0.0.1:11434/api/tags` (stdlib `urllib`)
3. Else only “use config default” + tip to start Ollama / `repolens init --provider ollama`

Selected model maps to `--model NAME` unless user picks config default (omit flag).

## 6. Execution & errors

- Build an argv list; never interpolate user paths into a shell string for execution.
- Fail fast with a clear message if `repolens` is missing from `PATH`.
- Ctrl+C / decline confirm → exit 0 without running.
- On confirm, `subprocess.run(argv)` (or equivalent) and exit with that process’s return code.
- Invalid menu input → re-prompt; do not crash.

## 7. Testing

- Pure helpers: menu/choice → argv; parse `ollama list` text; parse tags JSON.
- `tests/test_guided_script.py` imports helpers via `sys.path` insert of `scripts/` (or load by path).
- No CI test that starts Ollama or runs a full review.
- Optional smoke: shell launcher exists and is executable (lightweight).

## 8. Non-goals (v1)

- `repolens wizard` Typer command
- PowerShell twin
- Writing or mutating user/project config
- Auto-installing Ollama models
- Visual TUI (curses / rich required)

## 9. Acceptance

- From a checkout with `repolens` installed: `./scripts/repolens-guided.sh` (or `python3 scripts/repolens_guided.py`) walks the flow, prints a valid command, and on **Y** runs it.
- Choosing scanners-only never prompts for model.
- With Ollama up and models installed, the model menu lists those names.
- Unit tests for argv mapping and model parsing pass in CI.
