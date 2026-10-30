"""Record the CI benchmark arm, or print a before/after table."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repolens.benchmark_ci import ci_control_row, run_ci_arm
from repolens.benchmark_summary import compare_rows, require_arm
from repolens.config import RepoLensConfig, load_config

_SUMMARY_PAIR = 2
_JSON_INDENT = 2
_ROW_LATER = (
    "The benchmark row writer is not on this tree yet. "
    "--arm ci writes the zero-token control. --summary compares two JSON rows."
)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.summary:
        left = json.loads(Path(args.summary[0]).read_text(encoding="utf-8"))
        right = json.loads(Path(args.summary[1]).read_text(encoding="utf-8"))
        print(compare_rows(left, right))
        return 0
    if args.path is None or args.arm is None:
        parser.error("--path and --arm are required unless --summary is set")
    if args.arm != "ci":
        require_arm(load_config(args.path).model.provider, args.arm)
        raise SystemExit(_ROW_LATER)
    return _write_ci(args.path, args.label, args.out)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record the CI benchmark arm, or compare a before row with an after row."
    )
    parser.add_argument("--summary", nargs=_SUMMARY_PAIR, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--path", type=Path)
    parser.add_argument("--arm", choices=("local", "byok", "ci"))
    parser.add_argument("--label", default="run")
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks"))
    return parser


def _write_ci(path: Path, label: str, out: Path) -> int:
    print(
        "CI arm: no model. Scanners and Fast Brain still run. "
        "Phase lines follow. A line every 15 seconds means the run is still going.",
        file=sys.stderr,
    )
    report = run_ci_arm(path, RepoLensConfig(), out / "reports")
    row = ci_control_row(report, label=label, fixture=str(path))
    out.mkdir(parents=True, exist_ok=True)
    destination = out / f"{label}.json"
    destination.write_text(json.dumps(row, indent=_JSON_INDENT) + "\n", encoding="utf-8")
    wall = report.durationSeconds
    if wall is None:
        print(destination)
    else:
        print(f"{destination} ({wall:.1f}s)")
    return 0
