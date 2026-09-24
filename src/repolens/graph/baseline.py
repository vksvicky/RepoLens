"""Cyclicity baseline encode, load, and save (G2)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from repolens.config import GraphConfig
from repolens.graph.types import GraphResult

DEFAULT_BASELINE_PATH = ".repolens/baseline.json"

_GRAPH_ENGINE = "grimp"


def fingerprint_cycles(result: GraphResult) -> list[list[str]]:
    """One sorted module list per SCC with n≥2; outer list lexicographically sorted."""
    fps: list[list[str]] = []
    for group in result.cycles:
        if len(group.modules) < 2:
            continue
        fps.append(sorted(group.modules))
    fps.sort()
    return fps


def config_snapshot_from_graph_config(cfg: GraphConfig) -> dict[str, str]:
    return {
        "type_only": cfg.type_only,
        "local_imports": cfg.local_imports,
    }


def _utc_timestamp_z() -> str:
    return (
        datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def baseline_from_graph(
    result: GraphResult,
    *,
    config: GraphConfig,
    version: str,
) -> dict:
    fingerprints = fingerprint_cycles(result)
    return {
        "schemaVersion": 1,
        "kind": "cyclicity",
        "generatedAt": _utc_timestamp_z(),
        "repolensVersion": version,
        "graph": {
            "engine": _GRAPH_ENGINE,
            "packages": list(result.packages),
            "moduleCount": result.module_count,
            "cyclicity": result.cyclicity,
            "cycleCount": len(fingerprints),
            "fingerprints": fingerprints,
        },
        "configSnapshot": config_snapshot_from_graph_config(config),
    }


def write_baseline(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def load_baseline(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        msg = f"baseline must be a JSON object: {path}"
        raise TypeError(msg)
    return loaded
