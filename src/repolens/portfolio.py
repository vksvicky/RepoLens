"""Offline multi-repo portfolio audit (Fast Brain + scanners by default)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from repolens.schema import FindingReport


@dataclass
class PortfolioRepoResult:
    name: str
    path: str
    ok: bool
    confidence: int | None
    critical: int | None
    high: int | None
    cyclicity: int | None
    report_dir: str | None
    error: str | None


@dataclass
class PortfolioRunResult:
    repos: list[PortfolioRepoResult]
    index_path: Path
    exit_code: int


def _run_repo_scanners(*, path: Path, out: Path, slow_brain: bool) -> None:
    """Invoke review scanners-only (or optional deep) for one repo."""
    from repolens.pipeline import run_review
    from repolens.progress import null_progress

    run_review(
        path=path,
        mode="review",
        out_dir=out,
        scanners="auto",
        scanners_only=not slow_brain,
        deep=True if slow_brain else False,
        fmt="both",
        progress=null_progress(),
    )


def _read_paths_file(paths_file: Path) -> list[Path]:
    lines = paths_file.read_text(encoding="utf-8").splitlines()
    roots: list[Path] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        roots.append(Path(line).expanduser())
    if not roots:
        raise ValueError(f"No repo paths in {paths_file}")
    return roots


def _summarize_report(report_dir: Path) -> tuple[int, int, int, int | None]:
    jsons = sorted(
        (
            p
            for p in report_dir.glob("gate_review_report_*.json")
            if not p.name.endswith(".sarif.json")
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not jsons:
        raise FileNotFoundError(f"No gate JSON under {report_dir}")
    report = FindingReport.model_validate_json(jsons[0].read_text(encoding="utf-8"))
    cyc = report.graph.cyclicity if report.graph else None
    return (
        report.confidence,
        report.summary.critical,
        report.summary.high,
        cyc,
    )


def write_portfolio_index(out_dir: Path, rows: list[PortfolioRepoResult]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.md"
    lines = [
        "# Portfolio audit rollup",
        "",
        "| Repo | Gate % | Critical/High | Cyclicity | Status |",
        "|------|-------:|--------------:|----------:|--------|",
    ]
    for row in rows:
        if row.ok:
            ch = f"{row.critical}/{row.high}"
            cyc = str(row.cyclicity) if row.cyclicity is not None else "n/a"
            conf = str(row.confidence) if row.confidence is not None else "n/a"
            status = f"[ok]({row.report_dir})" if row.report_dir else "ok"
        else:
            ch = "—"
            cyc = "—"
            conf = "—"
            status = f"FAILED: {row.error}"
        lines.append(
            f"| `{row.name}` | {conf} | {ch} | {cyc} | {status} |"
        )
    lines.extend(
        [
            "",
            "## Exit policy",
            "",
            "- **0** — every listed repo finished without error",
            "- **1** — one or more repos failed (batch continued; see Status)",
            "- **2** — paths file missing/empty or fatal setup error",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_portfolio(
    paths_file: Path,
    out_dir: Path,
    *,
    slow_brain: bool = False,
) -> PortfolioRunResult:
    """Run scanners (+ optional Slow Brain) per path; soft-fail and roll up."""
    roots = _read_paths_file(paths_file)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[PortfolioRepoResult] = []
    for root in roots:
        name = root.name or str(root)
        dest = out_dir / name
        try:
            resolved = root.resolve()
            if not resolved.is_dir():
                raise FileNotFoundError(f"Not a directory: {root}")
            _run_repo_scanners(path=resolved, out=dest, slow_brain=slow_brain)
            conf, crit, high, cyc = _summarize_report(dest)
            rows.append(
                PortfolioRepoResult(
                    name=name,
                    path=str(resolved),
                    ok=True,
                    confidence=conf,
                    critical=crit,
                    high=high,
                    cyclicity=cyc,
                    report_dir=str(dest),
                    error=None,
                )
            )
        except Exception as exc:  # soft-fail per repo
            rows.append(
                PortfolioRepoResult(
                    name=name,
                    path=str(root),
                    ok=False,
                    confidence=None,
                    critical=None,
                    high=None,
                    cyclicity=None,
                    report_dir=None,
                    error=str(exc)[:300],
                )
            )
    index = write_portfolio_index(out_dir, rows)
    # Machine-readable companion
    (out_dir / "index.json").write_text(
        json.dumps([row.__dict__ for row in rows], indent=2) + "\n",
        encoding="utf-8",
    )
    exit_code = 0 if all(r.ok for r in rows) else 1
    return PortfolioRunResult(repos=rows, index_path=index, exit_code=exit_code)
