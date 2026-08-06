"""Phase 6.10: domain pack registry + azure-sentinel heuristics."""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import FileEntry
from repolens.packs.azure_sentinel.heuristics import scan_azure_sentinel
from repolens.packs.registry import get_pack, list_packs, resolve_enabled_packs
from repolens.playbooks import playbooks_for_mode


def test_list_packs_includes_azure_sentinel() -> None:
    packs = {p.id: p for p in list_packs()}
    assert "azure-sentinel" in packs
    assert packs["azure-sentinel"].playbook_body.strip()


def test_resolve_enabled_unknown_ignored() -> None:
    assert resolve_enabled_packs(["azure-sentinel", "nope"]) == ["azure-sentinel"]
    assert resolve_enabled_packs([]) == []


def test_get_pack_unknown_raises() -> None:
    try:
        get_pack("missing-pack")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_azure_heuristic_finds_hardcoded_tenant(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        '{\n  "tenantId": "11111111-1111-1111-1111-111111111111"\n}\n',
        encoding="utf-8",
    )
    entry = FileEntry(
        path=path,
        relative="workflow.json",
        size=path.stat().st_size,
        priority_band=1,
    )
    issues = scan_azure_sentinel(tmp_path, [entry])
    assert any("tenant" in i.title.lower() for i in issues)
    assert all(i.category == "pack.azure_sentinel" for i in issues)
    assert all(i.source == "heuristic" for i in issues)


def test_azure_heuristic_finds_connector_secret(tmp_path: Path) -> None:
    path = tmp_path / "connections.json"
    path.write_text(
        '{\n  "clientSecret": "super-secret-value-here"\n}\n',
        encoding="utf-8",
    )
    entry = FileEntry(
        path=path,
        relative="connections.json",
        size=path.stat().st_size,
        priority_band=1,
    )
    issues = scan_azure_sentinel(tmp_path, [entry])
    assert any("secret" in i.title.lower() or "connector" in i.title.lower() for i in issues)


def test_sentinel_mode_unchanged_without_packs() -> None:
    books = playbooks_for_mode("sentinel")
    assert len(books) == 1
    assert books[0][0] == "P1 security"


def test_pack_heuristics_via_scanners_only(tmp_path: Path) -> None:
    from repolens.pipeline import run_review
    from repolens.progress import ReviewProgress

    (tmp_path / "workflow.json").write_text(
        '{\n  "tenantId": "11111111-1111-1111-1111-111111111111"\n}\n',
        encoding="utf-8",
    )
    out = tmp_path / "reports"
    result = run_review(
        path=tmp_path,
        mode="sentinel",
        scanners="off",
        scanners_only=True,
        out_dir=out,
        fmt="json",
        packs=["azure-sentinel"],
        progress=ReviewProgress(quiet=True),
    )
    assert any(i.category == "pack.azure_sentinel" for i in result.report.issues)


def test_build_prompt_includes_pack_playbook(tmp_path: Path) -> None:
    from repolens.inventory import FileEntry
    from repolens.pipeline.prompt import build_prompt

    src = tmp_path / "x.py"
    src.write_text("print('ok')\n", encoding="utf-8")
    entry = FileEntry(
        path=src,
        relative="x.py",
        size=src.stat().st_size,
        priority_band=1,
    )
    prompt = build_prompt(
        "sentinel",
        tmp_path,
        [entry],
        full_audit=False,
        pack_ids=["azure-sentinel"],
    )
    assert "Domain pack:" in prompt
    assert "Sentinel" in prompt or "Logic" in prompt
