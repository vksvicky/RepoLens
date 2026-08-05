"""CLI entry for the guided review wizard."""

from __future__ import annotations

import shutil
import subprocess
import sys

from guided.argv import build_argv, format_command
from guided.caps import full_pack_large_model_warning, probe_review_cli_caps
from guided.prompts import _collect_choices, _prompt_yes


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
