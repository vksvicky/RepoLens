"""Rules registry: resolve by id, project overrides, enabled filtering."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.rules.registry import get_rule, list_rules, load_enabled_rules


def test_default_rules_resolve_by_id() -> None:
    security = get_rule("security")
    architecture = get_rule("architecture")
    reliability = get_rule("reliability")

    assert security.id == "security"
    assert security.band == "p1"
    assert security.enabled is True
    assert "security" in security.title.lower() or len(security.body) > 50

    assert architecture.id == "architecture"
    assert architecture.band == "p3"
    assert architecture.enabled is True
    assert len(architecture.body) > 50

    assert reliability.id == "reliability"
    assert reliability.band == "p2"
    assert reliability.enabled is True
    assert "reliability" in reliability.body.lower() or "bug" in reliability.body.lower()


def test_list_rules_defaults_exclude_disabled_unless_requested() -> None:
    enabled = list_rules()
    ids = {r.id for r in enabled}
    assert {"security", "architecture", "reliability"} <= ids
    assert all(r.enabled for r in enabled)

    all_rules = list_rules(include_disabled=True)
    assert len(all_rules) >= len(enabled)


def test_project_override_body_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()

    rules_dir = tmp_path / ".repolens" / "rules"
    rules_dir.mkdir(parents=True)
    override_body = "# Project security override\n\nCustom project security rule body.\n"
    (rules_dir / "security.md").write_text(override_body, encoding="utf-8")

    rule = get_rule("security", project_root=tmp_path)
    assert rule.body == override_body

    enabled = load_enabled_rules(project_root=tmp_path)
    by_id = {r.id: r for r in enabled}
    assert by_id["security"].body == override_body


def test_disabled_rule_omitted_from_load_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()

    conf = tmp_path / ".repolens"
    conf.mkdir()
    (conf / "rules.json").write_text(
        '{"rules": {"reliability": {"enabled": false}}}\n',
        encoding="utf-8",
    )

    enabled = load_enabled_rules(project_root=tmp_path)
    ids = {r.id for r in enabled}
    assert "reliability" not in ids
    assert "security" in ids

    with_disabled = list_rules(include_disabled=True, project_root=tmp_path)
    rel = next(r for r in with_disabled if r.id == "reliability")
    assert rel.enabled is False


def test_load_enabled_rules_band_filter() -> None:
    p1 = load_enabled_rules(band="p1")
    assert p1
    assert all(r.band == "p1" for r in p1)
    assert any(r.id == "security" for r in p1)


def test_get_rule_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_rule("does-not-exist")
