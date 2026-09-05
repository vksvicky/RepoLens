# tests/test_coverage_seeding.py
from repolens.coverage import evaluate_coverage
from repolens.schema import Issue, Severity
from repolens.themes import build_theme_breakdown


def test_seeded_na_clears_missed_without_llm_gaps():
    result = evaluate_coverage(
        ["sec.xss_csrf", "sec.injection"],
        [],
        [],
        seeded_na={"sec.xss_csrf": "desktop app; no HTML/DOM surface"},
        seeded_covered={},
    )
    assert "sec.xss_csrf" in result.na
    assert result.na["sec.xss_csrf"] == "desktop app; no HTML/DOM surface"
    assert "sec.injection" in result.missed


def test_seeded_covered_clears_missed_and_keeps_note():
    reason = "Audited: no SQL or shell sinks"
    result = evaluate_coverage(
        ["sec.injection"],
        [],
        [],
        seeded_na={},
        seeded_covered={"sec.injection": reason},
    )
    assert "sec.injection" in result.covered
    assert result.covered_notes["sec.injection"] == reason
    assert "sec.injection" not in result.missed


def test_issue_beats_seeded_na():
    issue = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.injection",
        file="x.rs",
        line=1,
        title="sec.injection sink",
        explanation="command injection",
        impact="Attacker may exploit command injection.",
        recommendedFix="fix",
        codeExample="exec(user_input)",
        fixTiming="immediately",
    )
    result = evaluate_coverage(
        ["sec.injection"],
        [issue],
        [],
        seeded_na={"sec.injection": "desktop app; out of scope"},
        seeded_covered={},
    )
    assert "sec.injection" in result.covered
    assert "sec.injection" not in result.na
    # Finding-backed cover: no seed note required
    assert "sec.injection" not in result.covered_notes


def test_lazy_seeded_na_becomes_missed():
    result = evaluate_coverage(
        ["sec.xss_csrf"],
        [],
        [],
        seeded_na={"sec.xss_csrf": "not reviewed"},
        seeded_covered={},
    )
    assert "sec.xss_csrf" in result.missed
    assert "sec.xss_csrf" in result.invalid_na


def test_issue_beats_seeded_covered():
    issue = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.injection",
        file="x.rs",
        line=1,
        title="sec.injection sink",
        explanation="command injection",
        impact="Attacker may exploit command injection.",
        recommendedFix="fix",
        codeExample="exec(user_input)",
        fixTiming="immediately",
    )
    result = evaluate_coverage(
        ["sec.injection"],
        [issue],
        [],
        seeded_na={},
        seeded_covered={"sec.injection": "Audited: no SQL or shell sinks"},
    )
    assert "sec.injection" in result.covered
    assert "sec.injection" not in result.covered_notes


def test_gap_na_beats_seeded_na_same_id():
    result = evaluate_coverage(
        ["sec.xss_csrf"],
        [],
        ["coverage:sec.xss_csrf: N/A — LLM gap reason overrides seed"],
        seeded_na={"sec.xss_csrf": "Seed reason from project config"},
        seeded_covered={},
    )
    assert "sec.xss_csrf" in result.na
    assert result.na["sec.xss_csrf"] == "LLM gap reason overrides seed"
    assert "sec.xss_csrf" not in result.missed


def test_seeded_covered_beats_seeded_na_same_id():
    result = evaluate_coverage(
        ["arch.testing"],
        [],
        [],
        seeded_na={"arch.testing": "desktop app; out of scope"},
        seeded_covered={"arch.testing": "Audited: cargo test + free-helpers gate"},
    )
    assert "arch.testing" in result.covered
    assert result.covered_notes["arch.testing"].startswith("Audited:")


def test_theme_breakdown_notes_from_seeds():
    """Seed strings must appear in Theme Breakdown Notes (Markdown ledger)."""
    cov = evaluate_coverage(
        ["sec.injection", "sec.xss_csrf"],
        [],
        [],
        seeded_na={"sec.xss_csrf": "Native desktop app; no web/DOM attack surface"},
        seeded_covered={
            "sec.injection": "Audited: no SQL or shell=True sinks in reviewed pack"
        },
    )
    themes = build_theme_breakdown(cov, [], mode="review", full_audit=False)
    by_id = {t.id: t for t in themes}
    assert by_id["sec.injection"].status == "covered"
    assert by_id["sec.injection"].notes.startswith("Audited:")
    assert by_id["sec.xss_csrf"].status == "na"
    assert "desktop" in by_id["sec.xss_csrf"].notes.lower()
