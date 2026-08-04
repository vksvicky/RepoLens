#!/usr/bin/env python3
"""Interactive guided helper for building and running a repolens command."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

RemoteKind = Literal["github", "git-url", "bitbucket", "hf"]


def _has_cli_flag(help_text: str, flag: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", help_text) is not None


def default_local_path(environ: Mapping[str, str] | None = None) -> str:
    """Prefer TARGET / REPOLENS_PATH when set (docs use TARGET=…); else cwd."""
    env = os.environ if environ is None else environ
    for key in ("TARGET", "REPOLENS_PATH"):
        raw = (env.get(key) or "").strip()
        if raw:
            return str(Path(raw).expanduser())
    return "."


def suggest_timeout_seconds(model: str | None) -> float:
    """Default HTTP timeout hint from model size tags in the name."""
    name = (model or "").lower()
    if re.search(r"(?<!\d)(70|72|65)b\b", name):
        return 3600.0
    if re.search(r"(?<!\d)32b\b", name):
        return 3600.0
    if re.search(r"(?<!\d)14b\b", name):
        return 1800.0
    return 900.0


def is_large_local_model(model: str | None) -> bool:
    """True when the name looks like a heavy local LLM (14B+)."""
    return suggest_timeout_seconds(model) >= 1800.0


def full_pack_large_model_warning(
    *,
    model: str | None,
    force_full: bool,
    force_changed: bool,
) -> str | None:
    """Warn when a large model is paired with a likely full LLM pack."""
    if not is_large_local_model(model) or force_changed:
        return None
    if force_full:
        pack = "forced full pack (--full)"
    else:
        pack = "adaptive pack (unchanged repos stay full)"
    return (
        f"Warning: {model} is a large local model with a likely {pack}. "
        "Expect a very large prompt and long runtimes; prefer "
        "'Changed files only', or set timeout to "
        f"{int(suggest_timeout_seconds(model))}s+."
    )


@dataclass(frozen=True)
class ReviewCliCaps:
    """Flags present in `repolens review --help` for this install."""

    supports_verbose: bool
    supports_timeout: bool
    supports_full: bool
    supports_changed: bool
    supports_deep: bool


@dataclass
class GuidedChoices:
    command: Literal["review", "sentinel", "architecture"]
    path: str | None
    out: str | None
    scanners_only: bool
    dry_run: bool
    force_full: bool
    force_changed: bool
    full_audit: bool
    model: str | None
    verbose: bool
    timeout: float | None
    fmt: str
    scanners: str
    fail_on: str | None
    remote: tuple[RemoteKind, str] | None
    ref: str | None
    deep: bool | None = None


def probe_review_cli_caps() -> ReviewCliCaps:
    """Probe once which optional review flags the local CLI documents."""
    try:
        proc = subprocess.run(
            ["repolens", "review", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        help_text = f"{proc.stdout or ''}{proc.stderr or ''}"
    except (OSError, subprocess.SubprocessError):
        help_text = ""
    return ReviewCliCaps(
        supports_verbose=_has_cli_flag(help_text, "--verbose"),
        supports_timeout=_has_cli_flag(help_text, "--timeout"),
        supports_full=_has_cli_flag(help_text, "--full"),
        supports_changed=_has_cli_flag(help_text, "--changed"),
        supports_deep=_has_cli_flag(help_text, "--deep"),
    )


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


def parse_ollama_tags_json(payload: Mapping[str, Any] | object) -> list[str]:
    if not isinstance(payload, dict):
        return []
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
        path = str(Path(choices.path or ".").expanduser())
        argv.extend(["--path", path])
    if choices.out:
        argv.extend(["--out", str(Path(choices.out).expanduser())])
    if choices.scanners_only:
        argv.append("--scanners-only")
    if choices.dry_run:
        argv.append("--dry-run")
    if choices.force_full and not choices.scanners_only and not choices.dry_run:
        argv.append("--full")
    if choices.force_changed and not choices.scanners_only and not choices.dry_run:
        argv.append("--changed")
    llm_pack = (
        choices.full_audit
        and choices.command == "review"
        and not choices.scanners_only
        and not choices.dry_run
    )
    if llm_pack:
        argv.append("--full-audit")
    if (
        choices.deep is not None
        and not choices.scanners_only
        and not choices.dry_run
    ):
        argv.append("--deep" if choices.deep else "--no-deep")
    if (
        choices.model
        and not choices.scanners_only
        and not choices.dry_run
    ):
        argv.extend(["--model", choices.model])
    if choices.verbose:
        argv.append("--verbose")
    if (
        choices.timeout is not None
        and not choices.scanners_only
        and not choices.dry_run
    ):
        # strip trailing .0 for integers
        t = (
            str(int(choices.timeout))
            if float(choices.timeout).is_integer()
            else str(choices.timeout)
        )
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
    except (
        OSError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        ValueError,
    ):
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
    """Show a numbered menu; return 1-based index. options are (label, tip)."""
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


def _collect_choices(caps: ReviewCliCaps | None = None) -> GuidedChoices:
    caps = caps if caps is not None else probe_review_cli_caps()

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
        path_default = default_local_path()
        if path_default != ".":
            src = (
                "TARGET"
                if (os.environ.get("TARGET") or "").strip()
                else "REPOLENS_PATH"
            )
            print(f"(default from ${src}: {path_default})")
        path_raw = _prompt_text("Repository path", path_default)
        path = str(Path(path_raw).expanduser())
        default_out = str(Path(path) / "reports")
        out_raw = _prompt_text("Report output directory", default_out)
        out = str(Path(out_raw or default_out).expanduser())
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
        kind_map: list[RemoteKind] = [
            "github",
            "git-url",
            "bitbucket",
            "hf",
        ]
        kind = kind_map[remote_kind_idx - 1]
        flag_name = "git-url" if kind == "git-url" else kind
        value = _prompt_text(f"Value for --{flag_name}")
        remote = (kind, value)
        ref_raw = input(
            "Optional --ref (branch/tag/commit) [none]: "
        ).strip()
        ref = ref_raw or None
        out = str(Path(_prompt_text("Report output directory", "./reports")).expanduser())

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

    depth_options: list[tuple[str, str]] = [
        ("Scanners only", "--scanners-only — no LLM; seconds"),
        ("Dry-run inventory", "--dry-run — list what would run"),
        (
            "Adaptive LLM",
            "smaller pack when files change; unchanged re-run still full",
        ),
    ]
    if caps.supports_changed:
        depth_options.append(
            (
                "Changed files only",
                "--changed — skip LLM if cache shows no edits",
            ),
        )
    if caps.supports_full:
        depth_options.append(
            ("Force full LLM pack", "--full — first deep audit / cold cache"),
        )
    depth_idx = _prompt_choice(
        "LLM depth",
        depth_options,
        default=3,
    )
    depth_label = depth_options[depth_idx - 1][0]
    scanners_only = depth_label.startswith("Scanners")
    dry_run = depth_label.startswith("Dry-run")
    force_changed = depth_label.startswith("Changed")
    force_full = depth_label.startswith("Force full")
    llm_will_run = not scanners_only and not dry_run

    full_audit = False
    if command == "review" and llm_will_run:
        playbook_idx = _prompt_choice(
            "Playbook depth",
            [
                ("Scoped architecture", "default — focused architecture pass"),
                (
                    "Full architecture audit",
                    "--full-audit — deeper architecture review",
                ),
            ],
            default=1,
        )
        full_audit = playbook_idx == 2

    deep: bool | None = None
    if llm_will_run and caps.supports_deep:
        # Default Y for review / full-audit (and other LLM modes — deep is CLI default).
        deep_default = True
        if full_audit or command == "review":
            deep_hint = (
                "Enable deep coverage (--deep)? "
                "Recommended for full audits / large repos "
                "(heuristics + chunked P1→P3 + checklist coverage)"
            )
        else:
            deep_hint = (
                "Enable deep coverage (--deep)? "
                "Multi-pass + heuristics; --no-deep = single-shot"
            )
        deep = _prompt_yes(deep_hint, default=deep_default)

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

    warn = full_pack_large_model_warning(
        model=model,
        force_full=force_full,
        force_changed=force_changed,
    )
    if warn:
        print(f"\n{warn}")

    verbose = False
    if caps.supports_verbose:
        verbose = _prompt_yes("Enable --verbose?", default=True)

    timeout: float | None = None
    if llm_will_run and caps.supports_timeout:
        suggested = suggest_timeout_seconds(model)
        hint = (
            f"{int(suggested)}s suggested for this model size; "
            "'n'/'none' to omit"
        )
        while True:
            raw = input(f"Timeout seconds [{int(suggested)}] ({hint}): ").strip().lower()
            if not raw:
                timeout = suggested
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
                print(
                    f"Enter a positive number, empty for {int(suggested)}, "
                    "or n/none to omit."
                )

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
        force_changed=force_changed,
        full_audit=full_audit,
        model=model,
        verbose=verbose,
        timeout=timeout,
        fmt=fmt,
        scanners=scanners,
        fail_on=fail_on,
        remote=remote,
        ref=ref,
        deep=deep,
    )


def main() -> int:
    try:
        if shutil.which("repolens") is None:
            print(
                "repolens not found on PATH.\n"
                "Tip: install the package (pip/uv) and activate your venv, "
                "then retry.",
                file=sys.stderr,
            )
            return 2

        caps = probe_review_cli_caps()
        choices = _collect_choices(caps)
        argv = build_argv(choices)
        print("\nCommand:")
        print(f"  {format_command(argv)}")
        if choices.scanners_only or choices.dry_run:
            print("ETA tip: typically completes in seconds.")
        else:
            warn = full_pack_large_model_warning(
                model=choices.model,
                force_full=choices.force_full,
                force_changed=choices.force_changed,
            )
            if warn:
                print(warn)
                print(
                    "ETA tip: large local models on full packs often need "
                    "30–90+ minutes; repair retries double that."
                )
            else:
                print(
                    "ETA tip: local LLM may take several minutes "
                    "on cold/full packs."
                )

        if not _prompt_yes("Run this command?", default=True):
            print("Declined — not running.")
            return 0

        proc = subprocess.run(argv, check=False)
        return int(proc.returncode)
    except (KeyboardInterrupt, EOFError):
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
