"""Interactive prompts for the guided review wizard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from guided.argv import GuidedChoices
from guided.caps import (
    RemoteKind,
    default_local_path,
    full_pack_large_model_warning,
    list_installed_models,
    probe_review_cli_caps,
    suggest_timeout_seconds,
    validate_remote_value,
    ReviewCliCaps,
)


def _prompt_text(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            raw = input(f"{prompt}{suffix}: ").strip()
        except EOFError:
            if default is not None:
                return default
            print("Input ended; please provide a value.")
            continue
        if raw:
            return raw
        if default is not None:
            return default
        print("Please enter a value (cannot be empty).")


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


def _prompt_remote() -> tuple[tuple[RemoteKind, str], str | None, str]:
    """Prompt for remote kind/value/ref and report out directory."""
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
    flag_name = "git-url" if kind == "git-url" else kind
    while True:
        value = _prompt_text(f"Value for --{flag_name}")
        err = validate_remote_value(kind, value)
        if err is None:
            break
        print(f"Invalid --{flag_name}: {err}")
    ref_raw = input("Optional --ref (branch/tag/commit) [none]: ").strip()
    out = str(Path(_prompt_text("Report output directory", "./reports")).expanduser())
    return (kind, value.strip()), (ref_raw or None), out


def _collect_choices(caps: ReviewCliCaps | None = None) -> GuidedChoices:
    caps = caps if caps is not None else probe_review_cli_caps()

    source = _prompt_choice(
        "Source",
        [
            ("Local path", "analyse a checkout on disk"),
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
        remote, ref, out = _prompt_remote()

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

