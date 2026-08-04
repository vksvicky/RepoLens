# Guided Review Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an interactive guided helper (`scripts/repolens_guided.py` + Bash launcher) that builds a correct `repolens` command with inline recommendations, confirms with the user, then runs it.

**Architecture:** Stdlib-only Python wizard owns menus, Ollama discovery, argv construction, confirm-then-run. Bash launcher only locates Python and execs the wizard. Unit tests import pure helpers via `sys.path` insert of `scripts/`; no package import of `repolens`, no live Ollama in CI.

**Tech Stack:** Python 3.11+ stdlib (`subprocess`, `urllib.request`, `json`, `shlex`, `shutil`, `pathlib`), Bash, pytest.

## Global Constraints

- Standalone scripts under `scripts/` — **not** a Typer subcommand (v1)
- Stdlib-only Python; require `repolens` on `PATH`; do not import `repolens` package
- Confirm Y/n before run; forward `repolens` exit code
- Local path first; remotes as advanced branch
- Wizard does **not** write `config.toml`
- No PowerShell twin; no auto-install of Ollama models

**Spec:** [docs/superpowers/specs/2026-08-03-guided-review-script-design.md](../specs/2026-08-03-guided-review-script-design.md)

## File structure

| Path | Responsibility |
|------|----------------|
| `scripts/repolens_guided.py` | Pure helpers + interactive `main()` |
| `scripts/repolens-guided.sh` | Thin `python3`/`python` launcher |
| `tests/test_guided_script.py` | Unit tests for helpers |
| `docs/try-on-your-repo.md` | Guided review subsection |
| `README.md` | One-line pointer |
| `docs/CHANGELOG.md` | Unreleased note |

---

### Task 1: Pure helpers + unit tests (TDD)

**Files:**
- Create: `scripts/repolens_guided.py`
- Create: `tests/test_guided_script.py`

**Interfaces:**
- Produces:
  - `parse_ollama_list(text: str) -> list[str]`
  - `parse_ollama_tags_json(payload: dict) -> list[str]`
  - `build_argv(choices: GuidedChoices) -> list[str]`
  - `@dataclass GuidedChoices` with fields used by `build_argv`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_guided_script.py
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from repolens_guided import (  # noqa: E402
    GuidedChoices,
    build_argv,
    parse_ollama_list,
    parse_ollama_tags_json,
)


def test_parse_ollama_list_skips_header() -> None:
    text = """NAME           ID       SIZE
qwen2.5:7b     abc      4.7 GB
llama3.2:3b    def      2.0 GB
"""
    assert parse_ollama_list(text) == ["qwen2.5:7b", "llama3.2:3b"]


def test_parse_ollama_tags_json() -> None:
    payload = {
        "models": [
            {"name": "qwen2.5:7b"},
            {"model": "mistral:7b"},
            {"name": ""},
        ]
    }
    assert parse_ollama_tags_json(payload) == ["qwen2.5:7b", "mistral:7b"]


def test_build_argv_local_review_adaptive() -> None:
    choices = GuidedChoices(
        command="review",
        path="/tmp/demo",
        out="/tmp/demo/reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        full_audit=False,
        model=None,
        verbose=True,
        timeout=900.0,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
    )
    argv = build_argv(choices)
    assert argv[:3] == ["repolens", "review", "--path"]
    assert "--path" in argv and "/tmp/demo" in argv
    assert "--out" in argv and "/tmp/demo/reports" in argv
    assert "--verbose" in argv
    assert "--timeout" in argv and "900" in argv
    assert "--scanners-only" not in argv
    assert "--full" not in argv
    assert "--model" not in argv


def test_build_argv_scanners_only_sentinel() -> None:
    choices = GuidedChoices(
        command="sentinel",
        path=".",
        out="./reports",
        scanners_only=True,
        dry_run=False,
        force_full=False,
        full_audit=False,
        model="qwen2.5:7b",  # must be ignored when scanners_only
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on="HIGH",
        remote=None,
        ref=None,
    )
    argv = build_argv(choices)
    assert argv[1] == "sentinel"
    assert "--scanners-only" in argv
    assert "--model" not in argv
    assert "--fail-on" in argv and "HIGH" in argv


def test_build_argv_github_remote() -> None:
    choices = GuidedChoices(
        command="review",
        path=None,
        out="/tmp/out",
        scanners_only=False,
        dry_run=False,
        force_full=True,
        full_audit=True,
        model="llama3.2:3b",
        verbose=True,
        timeout=1800.0,
        fmt="both",
        scanners="off",
        fail_on=None,
        remote=("github", "owner/repo"),
        ref="main",
    )
    argv = build_argv(choices)
    assert "--github" in argv and "owner/repo" in argv
    assert "--ref" in argv and "main" in argv
    assert "--path" not in argv
    assert "--full" in argv
    assert "--full-audit" in argv
    assert "--model" in argv and "llama3.2:3b" in argv
    assert "--format" in argv and "both" in argv
    assert "--scanners" in argv and "off" in argv
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_guided_script.py -v`  
Expected: FAIL (import / module not found)

- [ ] **Step 3: Implement helpers in `scripts/repolens_guided.py`**

```python
#!/usr/bin/env python3
"""Interactive guided helper for building and running a repolens command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RemoteKind = Literal["github", "git-url", "bitbucket", "hf"]


@dataclass
class GuidedChoices:
    command: Literal["review", "sentinel", "architecture"]
    path: str | None
    out: str | None
    scanners_only: bool
    dry_run: bool
    force_full: bool
    full_audit: bool
    model: str | None
    verbose: bool
    timeout: float | None
    fmt: str
    scanners: str
    fail_on: str | None
    remote: tuple[RemoteKind, str] | None
    ref: str | None


def parse_ollama_list(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("NAME"):
            continue
        token = line.split()[0]
        if token and token.lower() != "name":
            names.append(token)
    return names


def parse_ollama_tags_json(payload: dict) -> list[str]:
    names: list[str] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name:
            names.append(str(name))
    return names


def build_argv(choices: GuidedChoices) -> list[str]:
    argv: list[str] = ["repolens", choices.command]
    if choices.remote:
        kind, value = choices.remote
        flag = {
            "github": "--github",
            "git-url": "--git-url",
            "bitbucket": "--bitbucket",
            "hf": "--hf",
        }[kind]
        argv.extend([flag, value])
        if choices.ref:
            argv.extend(["--ref", choices.ref])
    else:
        argv.extend(["--path", choices.path or "."])
    if choices.out:
        argv.extend(["--out", choices.out])
    if choices.scanners_only:
        argv.append("--scanners-only")
    if choices.dry_run:
        argv.append("--dry-run")
    if choices.force_full and not choices.scanners_only and not choices.dry_run:
        argv.append("--full")
    if choices.full_audit and choices.command == "review" and not choices.scanners_only and not choices.dry_run:
        argv.append("--full-audit")
    if (
        choices.model
        and not choices.scanners_only
        and not choices.dry_run
    ):
        argv.extend(["--model", choices.model])
    if choices.verbose:
        argv.append("--verbose")
    if choices.timeout is not None and not choices.scanners_only and not choices.dry_run:
        # strip trailing .0 for integers
        t = str(int(choices.timeout)) if float(choices.timeout).is_integer() else str(choices.timeout)
        argv.extend(["--timeout", t])
    if choices.fmt and choices.fmt != "md":
        argv.extend(["--format", choices.fmt])
    if choices.scanners and choices.scanners != "auto":
        argv.extend(["--scanners", choices.scanners])
    if choices.fail_on:
        argv.extend(["--fail-on", choices.fail_on])
    return argv
```

Leave `main()` as a stub for Task 2:

```python
def main() -> int:
    raise SystemExit("interactive UI not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_guided_script.py -v`  
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit** (when user asks to commit)

```bash
git add scripts/repolens_guided.py tests/test_guided_script.py
git commit -m "$(cat <<'EOF'
feat: add guided review argv helpers and unit tests

EOF
)"
```

---

### Task 2: Interactive wizard + Ollama discovery + confirm/run

**Files:**
- Modify: `scripts/repolens_guided.py`
- Create: `scripts/repolens-guided.sh`
- Modify: `tests/test_guided_script.py` (add parse / tip helpers if extracted)

**Interfaces:**
- Consumes: `GuidedChoices`, `build_argv`, `parse_ollama_list`, `parse_ollama_tags_json`
- Produces:
  - `list_installed_models() -> list[str]`
  - `format_command(argv: list[str]) -> str` via `shlex.join`
  - `main() -> int`

- [ ] **Step 1: Add test for `format_command` / shell joining**

```python
from repolens_guided import format_command

def test_format_command_quotes_spaces() -> None:
    assert "Demo Project" in format_command(
        ["repolens", "review", "--path", "/tmp/Demo Project"]
    )
```

- [ ] **Step 2: Implement discovery + interactive `main()`**

Key behaviors (implement with small private helpers `_prompt_choice`, `_prompt_yes`, `_prompt_text`):

1. Fail if `shutil.which("repolens")` is None — print tip to install / activate venv; return 2.
2. Source menu: local (default) vs advanced remote.
3. Review kind → `command`.
4. LLM depth → set `scanners_only` / `dry_run` / `force_full`.
5. If `command == "review"` and LLM will run → playbook depth (`full_audit`).
6. If LLM will run → `list_installed_models()`:
   - try `subprocess.run(["ollama", "list"], …)` → `parse_ollama_list`
   - else `urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1)` → `parse_ollama_tags_json`
   - menu: `0` config default + each model; print tip about 7B vs smaller
7. Extras: verbose (default Y), timeout (suggest 900; note 1800 for large/first), format, scanners, fail-on.
8. `argv = build_argv(choices)`; print `format_command(argv)` + ETA tip:
   - scanners-only / dry-run → “seconds”
   - else → “local LLM may take several minutes on cold/full packs”
9. Confirm Y/n (default Y). On n / empty decline → return 0.
10. `subprocess.run(argv)` → return its `returncode`.
11. Catch `KeyboardInterrupt` → print newline, return 0.

```python
def format_command(argv: list[str]) -> str:
    import shlex
    return shlex.join(argv)


def list_installed_models() -> list[str]:
    import json
    import subprocess
    import urllib.error
    import urllib.request

    try:
        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            names = parse_ollama_list(proc.stdout)
            if names:
                return names
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=1
        ) as resp:
            payload = json.loads(resp.read().decode())
        return parse_ollama_tags_json(payload)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return []
```

Bash launcher `scripts/repolens-guided.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${ROOT}/repolens_guided.py"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$PY" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$PY" "$@"
else
  echo "python3/python not found" >&2
  exit 127
fi
```

Make executable: `chmod +x scripts/repolens-guided.sh scripts/repolens_guided.py`

- [ ] **Step 3: Run unit tests**

Run: `pytest tests/test_guided_script.py -v`  
Expected: PASS

- [ ] **Step 4: Manual smoke (local, not CI)**

```bash
# decline confirm
printf '1\n.\n\n3\n1\nn\nn\n\n1\n1\nn\n' | python3 scripts/repolens_guided.py
# or interactively: ./scripts/repolens-guided.sh
```

Expected: prints a `repolens …` command; on `n` exits 0 without long LLM wait.

- [ ] **Step 5: Commit** (when user asks)

```bash
git add scripts/repolens_guided.py scripts/repolens-guided.sh tests/test_guided_script.py
git commit -m "$(cat <<'EOF'
feat: interactive guided review script with Ollama model picker

EOF
)"
```

---

### Task 3: Docs + CHANGELOG

**Files:**
- Modify: `docs/try-on-your-repo.md` (add subsection near init / first review)
- Modify: `README.md` (one line under Quick start or Try it)
- Modify: `docs/CHANGELOG.md` (Unreleased)

- [ ] **Step 1: Add Guided review docs**

In `docs/try-on-your-repo.md`, after AI init / before a long review example:

```markdown
## Guided review (interactive)

From a RepoLens checkout (with `repolens` on your `PATH`):

```bash
./scripts/repolens-guided.sh
# or: python3 scripts/repolens_guided.py
```

The wizard asks for path, security/architecture/both, scanners-only vs full LLM,
installed Ollama models, timeout, and other flags — each option shows a short
recommendation. It prints the exact command and asks **Y/n** before running.
```

README one-liner:

```markdown
Interactive helper: `./scripts/repolens-guided.sh` (see [try-on-your-repo](docs/try-on-your-repo.md#guided-review-interactive)).
```

CHANGELOG under Unreleased:

```markdown
- Guided review script: `scripts/repolens-guided.sh` / `scripts/repolens_guided.py`
```

- [ ] **Step 2: Commit** (when user asks)

```bash
git add docs/try-on-your-repo.md README.md docs/CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs: document guided review helper script

EOF
)"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Python wizard + Bash launcher | 2 |
| Confirm Y/n then run | 2 |
| Local first + advanced remotes | 2 (`build_argv` in 1) |
| Review kind → review/sentinel/architecture | 1–2 |
| Scanners-only / dry-run / adaptive / `--full` | 1–2 |
| `--full-audit` for review + LLM | 1–2 |
| Ollama list → tags → config default | 2 |
| Extras: verbose, timeout, format, scanners, fail-on | 1–2 |
| Stdlib only / no `repolens` import | 1–2 |
| Unit tests, no live Ollama CI | 1 |
| Docs | 3 |

## Plan self-review

- No TBD/placeholder steps; signatures consistent (`GuidedChoices`, `build_argv`, `parse_ollama_*`).
- Non-goals respected (no Typer command, no PowerShell, no config writes).
- Commit steps noted as “when user asks” to honor repo commit policy.
