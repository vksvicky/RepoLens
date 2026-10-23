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
from repolens.pipeline.deep_job import DeepJob
from repolens.pipeline.prompt import _append_source_files
from repolens.progress import LlmGenerateProgress, ReviewProgress
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


def _run_deep_pass(job: DeepJob):
    idx = job.idx
    n = job.n
    deep_pass = job.deep_pass
    rules = job.rules
    pack_ids = job.pack_ids
    prompt_prefix = job.prompt_prefix
    cfg = job.cfg
    prog = job.prog
    raw_dir = job.raw_dir
    model_name = job.model_name
    provider = job.provider
    timeout = job.timeout
    file_work = job.file_work
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
    gen.file_work = file_work
    ollama_base = cfg.model.base_url if provider == "ollama" else None
    use_ollama = provider == "ollama"
    from repolens.pipeline.pass_timing import StreamClock

    clock = StreamClock()

    def on_delta(text: str) -> None:
        clock.note_chunk(text)
        gen.note_delta(text)

    def status_fn(progress: LlmGenerateProgress = gen) -> str | None:
        if use_ollama:
            return " | ".join(_ollama_wait_bits(progress, ollama_base))
        return progress.summary()

    clock.start()
    with prog.waiting(wait_label, hint=wait_hint, status_fn=status_fn):
        result = analyze_structured(
            prompt,
            cfg.model,
            pass_id=deep_pass.name,
            progress=prog,
            raw_dir=raw_dir,
            on_delta=on_delta,
        )
    clock.finish()
    gen.mark_done()
    report = _pass_report(result, deep_pass.name, prog)
    degraded = result.layer == "degraded" or result.report is None
    attempts = int(getattr(result, "repair_attempts", 0) or 0)
    chars_in = len(prompt)
    chars_out = len(result.raw_text or "")
    return report, result.raw_text or "", degraded, attempts, chars_in, chars_out, clock

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
    from repolens.llm.model_lock import queue_wait_seconds
    from repolens.llm_structured import analyze_structured
    from repolens.pipeline.pass_cache import closure_key, load_pass, save_pass
    from repolens.pipeline.pass_timing import (
        StreamClock,
        live_pass_timing,
        record_pass_timing,
        resumed_pass_timing,
    )

    model_name = cfg.model.model or default_model(cfg.model.provider)
    cached = load_pass(raw_dir.parent, closure_key(missed, model_name))
    if cached is not None:
        record_pass_timing(resumed_pass_timing("coverage"))
        prog.phase(
            "[Slow Brain] Resumed Coverage closure from cache "
            f"({len(cached.issues)} findings)"
        )
        return _merge_closure(report, cached)

    prog.phase(f"→ Coverage closure: {len(missed)} unanswered checklist id(s)…")
    provider = cfg.model.provider or "unknown"
    timeout = resolve_llm_timeout(cfg.model)
    gen = LlmGenerateProgress()
    clock = StreamClock()
    prompt = coverage_closure_prompt(missed)
    wait_before = queue_wait_seconds()

    def on_delta(text: str) -> None:
        clock.note_chunk(text)
        gen.note_delta(text)

    clock.start()
    with prog.waiting(
        f"Coverage closure — {model_name} via {provider} (timeout {timeout:g}s)",
        hint=f"{len(missed)} checklist id(s); no source re-pack",
        status_fn=lambda progress=gen: progress.summary(),
    ):
        result = analyze_structured(
            prompt,
            cfg.model,
            pass_id="coverage",
            progress=prog,
            raw_dir=raw_dir,
            on_delta=on_delta,
        )
    clock.finish()
    gen.mark_done()
    record_pass_timing(live_pass_timing(
        "coverage",
        queue_wait_seconds=round(max(0.0, queue_wait_seconds() - wait_before), 1),
        prompt_chars=len(prompt),
        raw_text=result.raw_text or "",
        clock=clock,
    ))
    if result.report is None:
        prog.phase("Coverage closure returned no report; unanswered ids stay missed")
        return report
    if result.layer != "degraded":
        save_pass(raw_dir.parent, closure_key(missed, model_name), result.report)
    return _merge_closure(report, result.report)
