"""Role-aware deep packs, outline budgeting, and rolling-summary cache keys."""

from __future__ import annotations

from pathlib import Path

from repolens.deep import (
    budget_files,
    compact_pass_summary,
    estimate_outline_chars,
    plan_deep_passes,
)
from repolens.inventory import FileEntry
from repolens.pipeline.pass_cache import pass_key
from repolens.rules.registry import Rule
from repolens.schema import FindingReport, Issue, Severity, Summary


def _entry(relative: str, size: int, *, band: int = 3) -> FileEntry:
    return FileEntry(
        path=Path("/tmp") / relative,
        relative=relative,
        size=size,
        priority_band=band,
    )


def _rule(rule_id: str, band: str) -> Rule:
    return Rule(
        id=rule_id,
        band=band,
        enabled=True,
        title=rule_id,
        body="body",
        coverage_ids=[f"{band}.a"],
    )


def _issue(title: str, file: str = "a.py") -> Issue:
    return Issue(
        severity=Severity.MEDIUM,
        priority="P1",
        category="sec.test",
        file=file,
        line=1,
        title=title,
        explanation="x",
        impact="",
        recommendedFix="fix",
        codeExample="",
    )


def test_estimate_outline_chars_is_much_smaller_than_raw_size() -> None:
    entry = _entry("src/big.py", 50_000)
    cost = estimate_outline_chars(entry)
    assert cost < entry.size // 5
    assert cost >= 80


def test_role_packs_give_each_band_its_own_file_list() -> None:
    rules = [
        _rule("security", "p1"),
        _rule("reliability", "p2"),
        _rule("architecture", "p3"),
    ]
    entries = [
        _entry("src/auth/login.py", 800),
        _entry("src/retry/backoff.py", 800),
        _entry("src/models/user.py", 800),
        _entry("assets/theme.css", 800),
    ]
    passes = plan_deep_passes(
        "review",
        full_audit=False,
        entries=entries,
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=1600,
        rules=rules,
        role_packs=True,
    )
    assert [p.name for p in passes] == ["p1", "p2", "p3"]
    p1_rels = [e.relative for e in passes[0].files]
    p2_rels = [e.relative for e in passes[1].files]
    assert "src/auth/login.py" in p1_rels
    assert "src/retry/backoff.py" in p2_rels
    assert passes[0].files != passes[1].files or p1_rels[0] != p2_rels[0]
    assert passes[2].pack_mode == "outline"
    assert passes[0].pack_mode == "full"


def test_role_packs_p3_fits_more_files_via_outline_budget() -> None:
    rules = [_rule("architecture", "p3")]
    # Ten large files: raw size budgeting fits ~1–2; outline budgeting fits many.
    entries = [_entry(f"src/mod_{i}.py", 40_000) for i in range(10)]
    raw = budget_files(entries, max_chars=50_000)
    passes = plan_deep_passes(
        "architecture",
        full_audit=True,
        entries=entries,
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=50_000,
        rules=rules,
        role_packs=True,
    )
    assert len(passes) == 1
    assert passes[0].pack_mode == "outline"
    assert len(passes[0].files) > len(raw)


def test_role_packs_off_keeps_shared_pack() -> None:
    rules = [
        _rule("security", "p1"),
        _rule("reliability", "p2"),
        _rule("architecture", "p3"),
    ]
    entries = [_entry("a.py", 100), _entry("b.py", 100)]
    passes = plan_deep_passes(
        "review",
        full_audit=False,
        entries=entries,
        hot_paths=[],
        adaptive_paths=[],
        chars_per_pass=10_000,
        rules=rules,
        role_packs=False,
    )
    assert passes[0].files == passes[1].files == passes[2].files
    assert all(p.pack_mode == "full" for p in passes)


def test_pass_key_changes_when_prior_summary_changes() -> None:
    entry = _entry("a.py", 10)
    first = pass_key([entry], "model", "p2", prior_summary="finding A")
    second = pass_key([entry], "model", "p2", prior_summary="finding B")
    third = pass_key([entry], "model", "p2")
    assert first != second
    assert first != third


def test_pass_key_changes_with_pack_mode_and_per_file_modes() -> None:
    entry = _entry("a.py", 10)
    outline = pass_key([entry], "model", "p3", pack_mode="outline")
    hybrid = pass_key(
        [entry],
        "model",
        "p3",
        pack_mode="hybrid",
        file_pack_modes={"a.py": "full"},
    )
    hybrid2 = pass_key(
        [entry],
        "model",
        "p3",
        pack_mode="hybrid",
        file_pack_modes={"a.py": "outline"},
    )
    assert outline != hybrid
    assert hybrid != hybrid2


def test_compact_pass_summary_is_short_and_lists_titles() -> None:
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[_issue("SQL injection"), _issue("Weak JWT")],
    )
    report.summary = report.recount_summary()
    text = compact_pass_summary(report, max_chars=800)
    assert "SQL injection" in text
    assert "Weak JWT" in text
    assert len(text) <= 800


def test_append_source_files_outline_mode_uses_structure_header(tmp_path: Path) -> None:
    from repolens.pipeline.prompt import _append_source_files

    src = tmp_path / "src" / "mod.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("def large():\n" + ("    x = 1\n" * 40), encoding="utf-8")
    entry = FileEntry(
        path=src,
        relative="src/mod.py",
        size=src.stat().st_size,
        priority_band=3,
    )
    text = _append_source_files("BASE", [entry], pack_mode="outline")
    assert "Structure outlines" in text
    assert "### src/mod.py" in text


def test_announce_role_packs_mentions_pack_modes() -> None:
    from unittest.mock import MagicMock

    from repolens.config import DeepConfig, ModelConfig, RepoLensConfig
    from repolens.deep import DeepPass
    from repolens.pipeline.deep_exec import _announce_deep_runtime

    prog = MagicMock()
    prog.quiet = False
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock"),
        deep=DeepConfig(role_packs=True),
    )
    passes = [
        DeepPass(name="p1", rule_ids=[], coverage_ids=[], files=[], pack_mode="full"),
        DeepPass(name="p3", rule_ids=[], coverage_ids=[], files=[], pack_mode="outline"),
    ]
    _announce_deep_runtime(prog, passes, cfg)
    detail_msgs = " ".join(str(c.args[0]) for c in prog.detail.call_args_list)
    assert "role_packs on" in detail_msgs
    assert "p3:outline" in detail_msgs


def test_deep_run_with_role_packs_journals_and_rolls_summary(
    tmp_path: Path, monkeypatch
) -> None:
    from unittest.mock import patch

    from repolens.config import AdaptiveConfig, DeepConfig, ModelConfig, RepoLensConfig
    from repolens.pipeline import run_review
    from repolens.pipeline.journal import read_events
    from tests.pipeline_deep_support import _pass_report

    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth_login.py").write_text("def login():\n    return 1\n", encoding="utf-8")
    (tmp_path / "src" / "retry_backoff.py").write_text(
        "def backoff():\n    return 2\n", encoding="utf-8"
    )
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True, role_packs=True),
    )
    prompts: dict[str, str] = {}

    def fake_analyze(
        prompt, model_cfg, *, pass_id, progress=None, raw_dir=None, on_delta=None, **_
    ):
        prompts[pass_id] = prompt
        return _pass_report(
            title=f"{pass_id} finding",
            file="src/auth_login.py",
            priority="P1" if pass_id == "p1" else "P2" if pass_id == "p2" else "P3",
            coverage_na=[],
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )

    assert "p1" in prompts and "p2" in prompts and "p3" in prompts
    assert "Prior pass findings" in prompts["p2"]
    assert "p1 finding" in prompts["p2"]
    assert "(Structure outlines" in prompts["p3"] or "Structure outlines" in prompts["p3"]

    events = read_events(tmp_path)
    kinds = [e["event"] for e in events]
    assert kinds.count("pass_started") >= 3
    assert kinds.count("pass_completed") >= 3
    completed = [e for e in events if e["event"] == "pass_completed" and not e.get("resumed")]
    assert any(e.get("chars_in", 0) > 0 for e in completed)
    assert any(e.get("role_packs") for e in events if e["event"] == "pass_started")
