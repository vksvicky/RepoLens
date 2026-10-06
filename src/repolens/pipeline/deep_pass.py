"""One deep-pass LLM call and the checklist closure follow-up."""

from __future__ import annotations

from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.deep import (
    build_deep_prompt,
    coverage_checklist_tail,
    coverage_closure_prompt,
)
from repolens.llm import default_model, resolve_llm_timeout
from repolens.pipeline.prompt import _append_source_files
from repolens.progress import LlmGenerateProgress, ReviewProgress
from repolens.rules.registry import Rule
from repolens.schema import FindingReport, Summary


def _ollama_wait_bits(progress: LlmGenerateProgress, base: str | None) -> list[str]:
    from repolens.provider_status import ollama_running_summary

    bits = [progress.summary()]
    live = ollama_running_summary(base)
    if live:
        bits.append(live)
    return bits


def _pass_report(result, pass_name: str, prog: ReviewProgress) -> FindingReport:
    if result.layer == "degraded":
        prog.phase(f"LLM: pass {pass_name} degraded — merging partial/empty result")
    if result.report is not None:
        return result.report
    return FindingReport(
        confidence=0,
        summary=Summary(),
        issues=[],
        durabilityGaps=[f"llm.schema_invalid:{pass_name}"],
    )


def _run_deep_pass(
    *,
    idx: int,
    n: int,
    deep_pass,
    rules: list[Rule],
    pack_ids: list,
    prompt_prefix: str,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    raw_dir: Path,
    model_name: str,
    provider: str,
    timeout: float,
) -> tuple[FindingReport, str, bool, int, int, int]:
    from repolens.llm_structured import analyze_structured

    prog.phase(f"→ Deep pass {idx}/{n} ({deep_pass.name})…")
    prompt = build_deep_prompt(
        deep_pass, rules, deep_pass.coverage_ids, pack_ids=pack_ids
    )
    pack_mode = getattr(deep_pass, "pack_mode", "full") or "full"
    prompt = _append_source_files(
        prompt,
        deep_pass.files,
        pack_mode=pack_mode,
        file_pack_modes=getattr(deep_pass, "file_pack_modes", None) or None,
    )
    prompt += coverage_checklist_tail(deep_pass.coverage_ids)
    if prompt_prefix:
        prompt = prompt_prefix + "\n\n" + prompt
    wait_label = (
        f"Deep pass {idx}/{n} ({deep_pass.name}) — {model_name} via {provider} "
        f"(timeout {timeout:g}s — large repos can take several minutes)"
    )
    wait_hint = (
        "streaming chat completions; "
        f"prompt ≈ {len(prompt):,} chars; "
        f"{len(deep_pass.files)} file(s); "
        f"mode={pack_mode}; "
        f"{len(deep_pass.coverage_ids)} coverage id(s)"
    )
    gen = LlmGenerateProgress()
    ollama_base = cfg.model.base_url if provider == "ollama" else None
    use_ollama = provider == "ollama"

    def status_fn(progress: LlmGenerateProgress = gen) -> str | None:
        if use_ollama:
            return " | ".join(_ollama_wait_bits(progress, ollama_base))
        return progress.summary()

    with prog.waiting(wait_label, hint=wait_hint, status_fn=status_fn):
        result = analyze_structured(
            prompt,
            cfg.model,
            pass_id=deep_pass.name,
            progress=prog,
            raw_dir=raw_dir,
            on_delta=gen.note_delta,
        )
    gen.mark_done()
    report = _pass_report(result, deep_pass.name, prog)
    degraded = result.layer == "degraded" or result.report is None
    attempts = int(getattr(result, "repair_attempts", 0) or 0)
    chars_in = len(prompt)
    chars_out = len(result.raw_text or "")
    return report, result.raw_text or "", degraded, attempts, chars_in, chars_out

def _merge_closure(report: FindingReport, extra: FindingReport) -> FindingReport:
    from repolens.deep import is_unmeasured_model_claim

    report.issues = list(report.issues) + [
        issue for issue in extra.issues if not is_unmeasured_model_claim(issue)
    ]
    report.durabilityGaps = list(report.durabilityGaps) + list(extra.durabilityGaps)
    report.summary = report.recount_summary()
    return report


def _apply_coverage_closure(
    report: FindingReport,
    missed: list[str],
    *,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    raw_dir: Path,
) -> FindingReport:
    """One short pass for checklist ids the band passes left unanswered."""
    if not missed:
        return report
    from repolens.llm_structured import analyze_structured
    from repolens.pipeline.pass_cache import closure_key, load_pass, save_pass

    model_name = cfg.model.model or default_model(cfg.model.provider)
    cached = load_pass(raw_dir.parent, closure_key(missed, model_name))
    if cached is not None:
        prog.phase(
            "[Slow Brain] Resumed Coverage closure from cache "
            f"({len(cached.issues)} findings)"
        )
        return _merge_closure(report, cached)

    prog.phase(f"→ Coverage closure: {len(missed)} unanswered checklist id(s)…")
    provider = cfg.model.provider or "unknown"
    timeout = resolve_llm_timeout(cfg.model)
    gen = LlmGenerateProgress()
    with prog.waiting(
        f"Coverage closure — {model_name} via {provider} (timeout {timeout:g}s)",
        hint=f"{len(missed)} checklist id(s); no source re-pack",
        status_fn=lambda progress=gen: progress.summary(),
    ):
        result = analyze_structured(
            coverage_closure_prompt(missed),
            cfg.model,
            pass_id="coverage",
            progress=prog,
            raw_dir=raw_dir,
            on_delta=gen.note_delta,
        )
    gen.mark_done()
    if result.report is None:
        prog.phase("Coverage closure returned no report; unanswered ids stay missed")
        return report
    if result.layer != "degraded":
        save_pass(raw_dir.parent, closure_key(missed, model_name), result.report)
    return _merge_closure(report, result.report)
