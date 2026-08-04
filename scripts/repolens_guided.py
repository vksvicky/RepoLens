#!/usr/bin/env python3
"""Interactive guided helper for building and running a repolens command."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
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


def format_command(argv: list[str]) -> str:
    return shlex.join(argv)


def list_installed_models() -> list[str]:
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


def _prompt_text(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default
        print("Please enter a value.")


def _prompt_yes(prompt: str, *, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _prompt_choice(
    title: str,
    options: list[tuple[str, str]],
    *,
    default: int = 1,
) -> int:
    """Show a numbered menu; return 1-based index. options are (label, recommendation)."""
    print(f"\n{title}")
    for i, (label, tip) in enumerate(options, start=1):
        mark = " (default)" if i == default else ""
        if tip:
            print(f"  {i}) {label}{mark} — {tip}")
        else:
            print(f"  {i}) {label}{mark}")
    while True:
        raw = input(f"Choice [{default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return idx
        print(f"Enter a number 1–{len(options)}.")


def _collect_choices() -> GuidedChoices:
    source = _prompt_choice(
        "Source",
        [
            ("Local path", "analyze a checkout on disk"),
            ("Advanced remote", "GitHub / git URL / Bitbucket / HF"),
        ],
        default=1,
    )

    path: str | None = None
    out: str | None = None
    remote: tuple[RemoteKind, str] | None = None
    ref: str | None = None

    if source == 1:
        path = _prompt_text("Repository path", ".")
        default_out = str(Path(path) / "reports")
        out_raw = _prompt_text("Report output directory", default_out)
        out = out_raw or default_out
    else:
        remote_kind_idx = _prompt_choice(
            "Remote kind",
            [
                ("GitHub owner/repo", "--github"),
                ("Git URL", "--git-url"),
                ("Bitbucket", "--bitbucket"),
                ("Hugging Face", "--hf"),
            ],
            default=1,
        )
        kind_map: list[RemoteKind] = ["github", "git-url", "bitbucket", "hf"]
        kind = kind_map[remote_kind_idx - 1]
        value = _prompt_text(f"Value for --{kind if kind != 'git-url' else 'git-url'}")
        remote = (kind, value)
        ref_raw = input("Optional --ref (branch/tag/commit) [none]: ").strip()
        ref = ref_raw or None
        out = _prompt_text("Report output directory", "./reports")

    kind_idx = _prompt_choice(
        "Review kind",
        [
            ("Security only", "repolens sentinel — fastest LLM playbook"),
            ("Architecture only", "repolens architecture"),
            ("Both", "repolens review — recommended default"),
        ],
        default=3,
    )
    command: Literal["review", "sentinel", "architecture"] = (
        "sentinel",
        "architecture",
        "review",
    )[kind_idx - 1]

    depth_idx = _prompt_choice(
        "LLM depth",
        [
            ("Scanners only", "--scanners-only — no LLM; seconds"),
            ("Dry-run inventory", "--dry-run — list what would run"),
            ("Adaptive LLM", "omit --full — warm runs use a smaller pack"),
            ("Force full LLM pack", "--full — first deep audit / cold cache"),
        ],
        default=3,
    )
    scanners_only = depth_idx == 1
    dry_run = depth_idx == 2
    force_full = depth_idx == 4
    llm_will_run = not scanners_only and not dry_run

    full_audit = False
    if command == "review" and llm_will_run:
        playbook_idx = _prompt_choice(
            "Playbook depth",
            [
                ("Scoped architecture", "default — focused architecture pass"),
                ("Full architecture audit", "--full-audit — deeper architecture review"),
            ],
            default=1,
        )
        full_audit = playbook_idx == 2

    model: str | None = None
    if llm_will_run:
        models = list_installed_models()
        print("\nModel")
        print("  0) Use config default (omit --model)")
        for i, name in enumerate(models, start=1):
            print(f"  {i}) {name}")
        if not models:
            print(
                "  (No models discovered — start Ollama or run: "
                "repolens init --provider ollama)"
            )
        print(
            "  Tip: smaller models are faster but weaker on schema; "
            "7B+ usually better for structured JSON."
        )
        while True:
            raw = input("Choice [0]: ").strip()
            if not raw or raw == "0":
                model = None
                break
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(models):
                    model = models[idx - 1]
                    break
            print(f"Enter 0–{len(models)}." if models else "Enter 0.")

    verbose = _prompt_yes("Enable --verbose?", default=True)

    timeout: float | None
    while True:
        raw = input(
            "Timeout seconds [900] (1800 for large/first run; 'n'/'none' to omit): "
        ).strip().lower()
        if not raw:
            timeout = 900.0
            break
        if raw in {"n", "no", "none"}:
            timeout = None
            break
        try:
            timeout = float(raw)
            if timeout <= 0:
                raise ValueError
            break
        except ValueError:
            print("Enter a positive number, empty for 900, or n/none to omit.")

    fmt_idx = _prompt_choice(
        "Report format",
        [
            ("Markdown", "md — default"),
            ("JSON", "json"),
            ("Both", "both"),
        ],
        default=1,
    )
    fmt = ("md", "json", "both")[fmt_idx - 1]

    scanners_idx = _prompt_choice(
        "Scanners",
        [
            ("Auto", "auto — use configured scanners (default)"),
            ("Off", "off — skip external scanners"),
        ],
        default=1,
    )
    scanners = ("auto", "off")[scanners_idx - 1]

    fail_idx = _prompt_choice(
        "Fail-on threshold",
        [
            ("None", "do not fail the process on findings (default)"),
            ("HIGH", "--fail-on HIGH"),
            ("CRITICAL", "--fail-on CRITICAL"),
        ],
        default=1,
    )
    fail_on = (None, "HIGH", "CRITICAL")[fail_idx - 1]

    return GuidedChoices(
        command=command,
        path=path,
        out=out,
        scanners_only=scanners_only,
        dry_run=dry_run,
        force_full=force_full,
        full_audit=full_audit,
        model=model,
        verbose=verbose,
        timeout=timeout,
        fmt=fmt,
        scanners=scanners,
        fail_on=fail_on,
        remote=remote,
        ref=ref,
    )


def main() -> int:
    try:
        if shutil.which("repolens") is None:
            print(
                "repolens not found on PATH.\n"
                "Tip: install the package (pip/uv) and activate your venv, then retry.",
                file=sys.stderr,
            )
            return 2

        choices = _collect_choices()
        argv = build_argv(choices)
        print("\nCommand:")
        print(f"  {format_command(argv)}")
        if choices.scanners_only or choices.dry_run:
            print("ETA tip: typically completes in seconds.")
        else:
            print(
                "ETA tip: local LLM may take several minutes on cold/full packs."
            )

        if not _prompt_yes("Run this command?", default=True):
            print("Declined — not running.")
            return 0

        proc = subprocess.run(argv, check=False)
        return int(proc.returncode)
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
