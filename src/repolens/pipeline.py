"""End-to-end review pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from repolens.config import ModelConfig, RepoLensConfig, load_config, resolve_report_dir
from repolens.inventory import FileEntry, list_files, read_excerpt
from repolens.llm import LlmError, analyze, repair_prompt
from repolens.playbooks import playbooks_for_mode
from repolens.report import write_json_report, write_markdown_report
from repolens.schema import FindingReport, Summary


@dataclass
class ReviewResult:
    report: FindingReport
    markdown_path: Path | None
    json_path: Path | None
    files_scanned: int
    dry_run: bool


def build_prompt(mode: str, root: Path, files: list[FileEntry], *, full_audit: bool) -> str:
    sections: list[str] = [
        f"Repository root: {root}",
        f"Mode: {mode}",
        f"Files provided: {len(files)}",
        "",
    ]
    for label, content in playbooks_for_mode(mode, full_audit=full_audit):
        sections.append(f"## Playbook: {label}")
        sections.append(content)
        sections.append("")

    sections.append("## Source files")
    for entry in files:
        sections.append(f"### {entry.relative} (priority band {entry.priority_band})")
        sections.append("```")
        sections.append(read_excerpt(entry))
        sections.append("```")
        sections.append("")
    sections.append("Analyze the files using the playbooks. Return FindingReport JSON only.")
    return "\n".join(sections)


def run_review(
    *,
    path: Path,
    mode: str,
    review_mode: str = "full",
    since: str | None = None,
    out_dir: Path | None = None,
    fmt: str = "md",
    model_override: str | None = None,
    full_audit: bool = False,
    dry_run: bool = False,
    trust_project: bool = False,
    config: RepoLensConfig | None = None,
) -> ReviewResult:
    root = path.resolve()
    cfg = config or load_config(root, trust_project=trust_project)
    if model_override:
        cfg.model.model = model_override

    files = list_files(root, mode=review_mode, since=since)
    if out_dir is not None:
        out = out_dir
    else:
        out = resolve_report_dir(root, cfg.general.report_dir)

    if dry_run:
        empty = FindingReport(
            confidence=0,
            summary=Summary(),
            issues=[],
            durabilityGaps=["dry-run: no LLM call"],
        )
        md = write_markdown_report(empty, out, mode=mode) if fmt in {"md", "both"} else None
        js = write_json_report(empty, out) if fmt in {"json", "both"} else None
        return ReviewResult(
            report=empty, markdown_path=md, json_path=js, files_scanned=len(files), dry_run=True
        )

    if not files:
        report = FindingReport(
            confidence=90,
            summary=Summary(),
            issues=[],
            durabilityGaps=["No reviewable files found (check ignores / --mode diff)"],
        )
    else:
        prompt = build_prompt(mode, root, files, full_audit=full_audit)
        report = _analyze_with_repair(prompt, cfg.model)

    md = write_markdown_report(report, out, mode=mode) if fmt in {"md", "both"} else None
    js = write_json_report(report, out) if fmt in {"json", "both"} else None
    return ReviewResult(
        report=report, markdown_path=md, json_path=js, files_scanned=len(files), dry_run=False
    )


def _analyze_with_repair(prompt: str, model_cfg: ModelConfig) -> FindingReport:
    try:
        return analyze(prompt, model_cfg)
    except (LlmError, ValidationError) as first_error:
        try:
            return analyze(repair_prompt(prompt, str(first_error)), model_cfg)
        except (LlmError, ValidationError) as second_error:
            msg = f"LLM analysis failed after repair attempt: {second_error}"
            raise LlmError(msg) from second_error


def fail_on_triggered(report: FindingReport, fail_on: str | None) -> bool:
    if not fail_on:
        return False
    order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    key = fail_on.upper()
    if key not in order:
        raise ValueError(
            f"Invalid --fail-on severity {fail_on!r}; use CRITICAL|HIGH|MEDIUM|LOW"
        )
    threshold = order[key]
    for issue in report.issues:
        if order[issue.severity.value] >= threshold:
            return True
    return False
