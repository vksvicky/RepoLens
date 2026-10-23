"""Record a finished model call and write the gate report files."""

from __future__ import annotations


def _record_llm_success(state) -> None:
    import time

    from repolens.adaptive import recommend_timeout
    from repolens.learning.store import RecordRun

    llm_seconds = time.time() - state.started
    state.llm_seconds_prov = round(time.monotonic() - state._llm_t0, 1)
    if state.store is None:
        return
    state.store.record_run(RecordRun(
        started_at=state.started,
        finished_at=time.time(),
        mode=state.mode,
        provider=state.cfg.model.provider,
        model=state.model_name,
        files_in_prompt=len(state.llm_files),
        llm_seconds=llm_seconds,
        timeout_used=state.timeout,
        outcome="ok",
    ))
    hist = state.store.successful_llm_seconds()
    rec = recommend_timeout(hist, adaptive=state.cfg.adaptive, file_count=len(state.llm_files))
    state.store.set_meta("recommended_timeout_seconds", f"{rec:g}")


def _persist_finished_artifacts(state):
    from datetime import UTC, datetime

    from repolens.pipeline.types import ReviewResult
    from repolens.report import write_json_report, write_markdown_report
    from repolens.sarif import write_sarif_report

    if state.report_when is None:
        state.report_when = datetime.now(UTC)
    state.prog.phase(f"Writing report → {state.out}")
    state.md = (
        write_markdown_report(state.report, state.out, mode=state.mode, when=state.report_when)
        if state.fmt in {"md", "both"}
        else None
    )
    state.js = (
        write_json_report(state.report, state.out, mode=state.mode, when=state.report_when)
        if state.fmt in {"json", "both"}
        else None
    )
    if state.js is not None:
        from repolens.explain import write_last_report_pointer

        write_last_report_pointer(state.root, state.js)
    elif state.md is not None and state.fmt == "md":
        state.js = write_json_report(
            state.report, state.out, mode=state.mode, when=state.report_when
        )
        from repolens.explain import write_last_report_pointer

        write_last_report_pointer(state.root, state.js)
    sarif_path = None
    if state.sarif:
        sarif_path = write_sarif_report(
            state.report, state.root, out_dir=state.out, mode=state.mode, when=state.report_when
        )
        if sarif_path is not None:
            n = sum(1 for i in state.report.issues if i.locationVerified)
            state.prog.detail(
                f"SARIF: {sarif_path.name} "
                f"({n}/{len(state.report.issues)} location-verified result(s))"
            )
    state.prog.phase("Done")
    return ReviewResult(
        report=state.report,
        markdown_path=state.md,
        json_path=state.js,
        files_scanned=state.fast_brain_file_count,
        dry_run=False,
        sarif_path=sarif_path,
        aborted=bool(state.aborted),
    )
