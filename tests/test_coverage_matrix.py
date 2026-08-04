"""Coverage matrix sync against default rule pack (no absolute author paths)."""

from __future__ import annotations

from pathlib import Path

from repolens.coverage import (
    coverage_ids_for_pass,
    evaluate_coverage,
    load_coverage_matrix,
    parse_coverage_notes,
)
from repolens.rules.registry import get_rule, list_rules
from repolens.schema import Issue, Severity


def test_every_coverage_id_has_rule_in_default_pack() -> None:
    matrix = load_coverage_matrix()
    default_ids = {r.id for r in list_rules(include_disabled=True)}
    assert matrix.entries, "coverage matrix must not be empty"
    for entry in matrix.entries:
        assert entry.rule_id, f"{entry.id} missing rule_id"
        assert entry.rule_id in default_ids, (
            f"coverage {entry.id} references unknown rule_id={entry.rule_id!r}"
        )


def test_anchors_resolve_in_rule_body_or_implicit() -> None:
    matrix = load_coverage_matrix()
    for entry in matrix.entries:
        rule = get_rule(entry.rule_id)
        anchor = entry.playbook_anchor
        if anchor is None or anchor == "implicit":
            continue
        assert anchor in rule.body, (
            f"coverage {entry.id} playbook_anchor={anchor!r} not found in rule "
            f"{entry.rule_id!r} body"
        )


def test_no_absolute_author_machine_paths_in_coverage_or_rules() -> None:
    forbidden = "/Users/vivek/Development"
    matrix = load_coverage_matrix()
    for entry in matrix.entries:
        joined = " ".join(
            [entry.id, entry.rule_id, entry.title, entry.playbook_anchor or ""]
        )
        assert forbidden not in joined
        rule = get_rule(entry.rule_id)
        assert forbidden not in rule.body
        assert forbidden not in rule.title

    # Also scan packaged default files under rules/defaults for path leakage
    defaults = Path(__file__).resolve().parents[1] / "src" / "repolens" / "rules" / "defaults"
    if defaults.is_dir():
        for path in defaults.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json"}:
                text = path.read_text(encoding="utf-8")
                assert forbidden not in text, f"absolute path leaked in {path}"


def test_coverage_ids_for_pass_respects_full_audit_and_enabled() -> None:
    enabled = {"security", "architecture", "reliability"}
    review_scoped = coverage_ids_for_pass(
        "p3", full_audit=False, enabled_rule_ids=enabled
    )
    review_full = coverage_ids_for_pass("p3", full_audit=True, enabled_rule_ids=enabled)
    assert set(review_scoped) <= set(review_full)

    disabled_arch = coverage_ids_for_pass(
        "p3", full_audit=True, enabled_rule_ids={"security", "reliability"}
    )
    matrix = load_coverage_matrix()
    arch_ids = {e.id for e in matrix.entries if e.rule_id == "architecture"}
    assert not (set(disabled_arch) & arch_ids)


def test_parse_coverage_notes_and_evaluate() -> None:
    notes = parse_coverage_notes(
        [
            "coverage:sec.injection: N/A — no SQL layer in pack",
            "unrelated durability note",
            "coverage:arch.testing: N/A — no test suite yet",
        ]
    )
    assert notes["sec.injection"] == "no SQL layer in pack"
    assert notes["arch.testing"] == "no test suite yet"
    assert "unrelated durability note" not in notes

    issues = [
        Issue(
            severity=Severity.MEDIUM,
            priority="P1",
            category="Injection",
            file="a.py",
            line=1,
            title="Possible command injection",
            explanation="e",
            impact="i",
            recommendedFix="f",
            codeExample="",
        )
    ]
    result = evaluate_coverage(
        ["sec.injection", "sec.secrets", "arch.testing"],
        issues,
        [
            "coverage:sec.injection: N/A — no SQL layer in pack",
            "coverage:arch.testing: N/A — deferred",
        ],
    )
    assert "sec.injection" in result.na
    assert "arch.testing" in result.na
    # secrets neither N/A nor clearly covered by title alone may be missed
    assert "sec.secrets" in result.missed or "sec.secrets" in result.covered
