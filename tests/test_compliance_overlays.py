"""Fintech / healthtech compliance overlays (#114)."""

from __future__ import annotations

from pathlib import Path

from repolens.config import PacksConfig
from repolens.inventory import FileEntry
from repolens.packs.fintech.heuristics import scan_fintech
from repolens.packs.healthtech.heuristics import scan_healthtech
from repolens.packs.registry import get_pack, list_packs, resolve_enabled_packs


def test_overlays_listed_and_namespaced() -> None:
    ids = {p.id for p in list_packs()}
    assert "fintech" in ids and "healthtech" in ids
    fin = get_pack("fintech")
    assert "fintech.pci_pan" in fin.playbook_body
    assert "Not a certification" in fin.playbook_body or "Not a QSA" in fin.description
    health = get_pack("healthtech")
    assert "healthtech.phi_logging" in health.playbook_body
    assert "HIPAA" in health.playbook_body or "HIPAA" in health.description


def test_packs_config_overlays_merge() -> None:
    cfg = PacksConfig(enabled=["fintech"], overlays=["healthtech", "fintech"])
    assert cfg.resolved() == ["fintech", "healthtech"]
    assert resolve_enabled_packs(cfg.resolved()) == ["fintech", "healthtech"]


def test_fintech_heuristic_flags_pan_log(tmp_path: Path) -> None:
    f = tmp_path / "pay.py"
    f.write_text("log.info('pan=%s', pan)\n", encoding="utf-8")
    entry = FileEntry(path=f, relative="pay.py", size=1, priority_band=1)
    issues = scan_fintech(tmp_path, [entry])
    assert issues and issues[0].category == "fintech.pci_pan"


def test_healthtech_heuristic_flags_phi_log(tmp_path: Path) -> None:
    f = tmp_path / "clinical.py"
    f.write_text("log.info('patient_id=%s', patient_id)\n", encoding="utf-8")
    entry = FileEntry(path=f, relative="clinical.py", size=1, priority_band=1)
    issues = scan_healthtech(tmp_path, [entry])
    assert issues and issues[0].category == "healthtech.phi_logging"
