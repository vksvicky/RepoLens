"""Domain pack discovery and resolution (Phase 6.10)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue

HeuristicFn = Callable[[Path, list[FileEntry]], list[Issue]]


@dataclass(frozen=True)
class DomainPack:
    id: str
    title: str
    description: str
    playbook_body: str
    run_heuristics: HeuristicFn | None = None


def _pack_root(pack_id: str) -> Path:
    here = Path(__file__).resolve().parent
    # Map azure-sentinel → azure_sentinel package dir
    dirname = pack_id.replace("-", "_")
    return here / dirname


def _load_playbook(pack_id: str) -> str:
    path = _pack_root(pack_id) / "playbook.md"
    if not path.is_file():
        raise FileNotFoundError(f"Pack playbook missing: {path}")
    return path.read_text(encoding="utf-8")


def _azure_sentinel_heuristics(root: Path, entries: list[FileEntry]) -> list[Issue]:
    from repolens.packs.azure_sentinel.heuristics import scan_azure_sentinel

    return scan_azure_sentinel(root, entries)


_PACKS: dict[str, DomainPack] | None = None


def _ensure_packs() -> dict[str, DomainPack]:
    global _PACKS
    if _PACKS is not None:
        return _PACKS
    _PACKS = {
        "azure-sentinel": DomainPack(
            id="azure-sentinel",
            title="Azure Sentinel / Logic Apps SOAR",
            description=(
                "Opt-in checks for Microsoft Sentinel analytics, Logic Apps, "
                "and SOAR workflows (tenant IDs, connector secrets, subscription IDs)."
            ),
            playbook_body=_load_playbook("azure-sentinel"),
            run_heuristics=_azure_sentinel_heuristics,
        )
    }
    return _PACKS


def list_packs() -> list[DomainPack]:
    return sorted(_ensure_packs().values(), key=lambda p: p.id)


def get_pack(pack_id: str) -> DomainPack:
    packs = _ensure_packs()
    if pack_id not in packs:
        raise KeyError(f"Unknown domain pack {pack_id!r}. Known: {sorted(packs)}")
    return packs[pack_id]


def resolve_enabled_packs(requested: list[str]) -> list[str]:
    """Return known pack ids from ``requested`` (stable order, deduped)."""
    known = _ensure_packs()
    out: list[str] = []
    seen: set[str] = set()
    for raw in requested:
        pid = (raw or "").strip().lower()
        if not pid or pid in seen or pid not in known:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def pack_playbook_sections(pack_ids: list[str]) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for pid in resolve_enabled_packs(pack_ids):
        pack = get_pack(pid)
        sections.append((f"Domain pack: {pack.title}", pack.playbook_body))
    return sections


def run_pack_heuristics(
    root: Path,
    entries: list[FileEntry],
    pack_ids: list[str],
) -> list[Issue]:
    issues: list[Issue] = []
    for pid in resolve_enabled_packs(pack_ids):
        pack = get_pack(pid)
        if pack.run_heuristics is None:
            continue
        issues.extend(pack.run_heuristics(root, entries))
    return issues
