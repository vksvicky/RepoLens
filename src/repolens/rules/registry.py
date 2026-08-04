"""Resolve review rules by id (project → user → packaged defaults)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Rule:
    id: str
    band: str
    enabled: bool
    title: str
    body: str
    coverage_ids: list[str] | None = None


def _defaults_dir() -> Path:
    try:
        root = resources.files("repolens.rules") / "defaults"
        if root.is_dir() and (root / "manifest.json").is_file():
            return Path(str(root))
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass

    here = Path(__file__).resolve().parent / "defaults"
    if (here / "manifest.json").is_file():
        return here
    raise FileNotFoundError(
        "Could not locate rules defaults pack (manifest.json). "
        "Ensure RepoLens is installed with package data."
    )


def _user_config_root() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "repolens"
    return Path.home() / ".config" / "repolens"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _load_manifest(defaults: Path) -> list[dict[str, Any]]:
    raw = _read_json(defaults / "manifest.json")
    rules = raw.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("defaults/manifest.json must contain a non-empty rules list")
    return rules


def _coverage_ids_by_rule(defaults: Path) -> dict[str, list[str]]:
    raw = _read_json(defaults / "coverage.json")
    entries = raw.get("entries", [])
    by_rule: dict[str, list[str]] = {}
    if not isinstance(entries, list):
        return by_rule
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rule_id = entry.get("rule_id")
        cov_id = entry.get("id")
        if isinstance(rule_id, str) and isinstance(cov_id, str):
            by_rule.setdefault(rule_id, []).append(cov_id)
    return by_rule


def _overlay_meta(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge per-rule override dict (enabled/title/band) onto base meta."""
    merged = dict(base)
    for key in ("enabled", "title", "band"):
        if key in overlay:
            merged[key] = overlay[key]
    return merged


def _collect_overrides(project_root: Path | None) -> dict[str, dict[str, Any]]:
    """Return rule_id → override fields from user then project (project wins)."""
    overrides: dict[str, dict[str, Any]] = {}

    user_root = _user_config_root()
    user_json = _read_json(user_root / "rules.json")
    user_rules = user_json.get("rules", {})
    if isinstance(user_rules, dict):
        for rule_id, meta in user_rules.items():
            if isinstance(rule_id, str) and isinstance(meta, dict):
                overrides[rule_id] = dict(meta)

    if project_root is not None:
        project_json = _read_json(project_root / ".repolens" / "rules.json")
        project_rules = project_json.get("rules", {})
        if isinstance(project_rules, dict):
            for rule_id, meta in project_rules.items():
                if isinstance(rule_id, str) and isinstance(meta, dict):
                    current = overrides.get(rule_id, {})
                    overrides[rule_id] = {**current, **meta}

    return overrides


def _safe_rule_id(rule_id: str) -> str:
    """Reject ids that could escape rules directories via path segments."""
    if not rule_id or rule_id in {".", ".."} or "/" in rule_id or "\\" in rule_id:
        raise ValueError(f"Invalid rule id: {rule_id!r}")
    return rule_id


def _safe_body_file(body_file: str) -> str:
    """Only allow a basename under the defaults pack (no path traversal)."""
    name = Path(body_file).name
    if not name or name != body_file or name in {".", ".."}:
        raise ValueError(f"Invalid body_file (basename only): {body_file!r}")
    return name


def _resolve_body(
    rule_id: str,
    *,
    body_file: str,
    defaults: Path,
    project_root: Path | None,
) -> str:
    rule_id = _safe_rule_id(rule_id)
    body_file = _safe_body_file(body_file)

    if project_root is not None:
        project_body = (project_root / ".repolens" / "rules" / f"{rule_id}.md").resolve()
        rules_root = (project_root / ".repolens" / "rules").resolve()
        if project_body.is_file() and project_body.is_relative_to(rules_root):
            return project_body.read_text(encoding="utf-8")

    user_rules = (_user_config_root() / "rules").resolve()
    user_body = (user_rules / f"{rule_id}.md").resolve()
    if user_body.is_file() and user_body.is_relative_to(user_rules):
        return user_body.read_text(encoding="utf-8")

    packaged = (defaults / body_file).resolve()
    defaults_resolved = defaults.resolve()
    if not packaged.is_file() or not packaged.is_relative_to(defaults_resolved):
        raise FileNotFoundError(f"Default rule body missing for id={rule_id!r}: {body_file}")
    return packaged.read_text(encoding="utf-8")


def _build_rules(*, project_root: Path | None = None) -> dict[str, Rule]:
    defaults = _defaults_dir()
    manifest = _load_manifest(defaults)
    coverage_map = _coverage_ids_by_rule(defaults)
    overlays = _collect_overrides(project_root)

    built: dict[str, Rule] = {}
    for item in manifest:
        if not isinstance(item, dict):
            continue
        rule_id = item.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("manifest rule missing id")
        body_file = item.get("body_file")
        if not isinstance(body_file, str) or not body_file:
            raise ValueError(f"manifest rule {rule_id!r} missing body_file")

        meta = dict(item)
        if rule_id in overlays:
            meta = _overlay_meta(meta, overlays[rule_id])

        enabled = bool(meta.get("enabled", True))
        band = str(meta.get("band", "p3")).lower()
        title = str(meta.get("title", rule_id))
        body = _resolve_body(
            rule_id,
            body_file=body_file,
            defaults=defaults,
            project_root=project_root,
        )
        cov_ids = coverage_map.get(rule_id) or None
        built[rule_id] = Rule(
            id=rule_id,
            band=band,
            enabled=enabled,
            title=title,
            body=body,
            coverage_ids=list(cov_ids) if cov_ids else None,
        )

    # Allow project/user overlays to introduce unknown ids? Out of scope — stick to pack ids.
    # Still apply enable/title overlays only for known ids (already done).

    # Re-apply overlay-only enable for rules that exist
    for rule_id, overlay in overlays.items():
        if rule_id in built and "enabled" in overlay:
            built[rule_id] = replace(built[rule_id], enabled=bool(overlay["enabled"]))
        if rule_id in built and "title" in overlay and isinstance(overlay["title"], str):
            built[rule_id] = replace(built[rule_id], title=overlay["title"])
        if rule_id in built and "band" in overlay and isinstance(overlay["band"], str):
            built[rule_id] = replace(built[rule_id], band=overlay["band"].lower())

    return built


def list_rules(
    *,
    include_disabled: bool = False,
    project_root: Path | None = None,
) -> list[Rule]:
    rules = list(_build_rules(project_root=project_root).values())
    rules.sort(key=lambda r: (r.band, r.id))
    if include_disabled:
        return rules
    return [r for r in rules if r.enabled]


def get_rule(rule_id: str, *, project_root: Path | None = None) -> Rule:
    rules = _build_rules(project_root=project_root)
    if rule_id not in rules:
        raise KeyError(f"Unknown rule id: {rule_id}")
    return rules[rule_id]


def load_enabled_rules(
    *,
    band: str | None = None,
    project_root: Path | None = None,
) -> list[Rule]:
    rules = list_rules(include_disabled=False, project_root=project_root)
    if band is None:
        return rules
    band_norm = band.lower()
    return [r for r in rules if r.band == band_norm]
