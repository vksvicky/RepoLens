"""Thin adapter: mode → ordered playbook labels/content via rules registry."""

from __future__ import annotations

from pathlib import Path

from repolens.rules.registry import get_rule


def playbooks_dir() -> Path:
    """Return directory containing packaged default rule bodies (compat)."""
    from importlib import resources

    try:
        root = resources.files("repolens.rules") / "defaults"
        if root.is_dir():
            return Path(str(root))
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass
    here = Path(__file__).resolve().parent / "rules" / "defaults"
    if here.is_dir():
        return here
    raise FileNotFoundError(
        "Could not locate rules defaults pack. Ensure RepoLens is installed with package data."
    )


def load_playbook(name: str) -> str:
    """Load a playbook by legacy filename or rule id (compat).

    Prefer ``get_rule(rule_id).body`` for new code.
    """
    rule_id = name.removesuffix(".md")
    try:
        return get_rule(rule_id).body
    except KeyError as exc:
        raise FileNotFoundError(f"Playbook not found for name={name!r}") from exc


def playbooks_for_mode(mode: str, *, full_audit: bool = False) -> list[tuple[str, str]]:
    """Return ordered (label, content) playbooks for a CLI mode."""
    if mode == "sentinel":
        rule = get_rule("security")
        return [("P1 security", rule.body)]
    if mode == "architecture":
        rule = get_rule("architecture")
        return [("P3 architecture", rule.body)]
    if mode == "review":
        security = get_rule("security")
        reliability = get_rule("reliability")
        architecture = get_rule("architecture")
        items: list[tuple[str, str]] = [
            ("P1 security", security.body),
            ("P2 reliability", reliability.body),
        ]
        if full_audit:
            items.append(("P3 architecture", architecture.body))
        else:
            items.append(
                (
                    "P3 architecture (scoped)",
                    (
                        "Perform a scoped architecture/quality review of the change blast radius. "
                        "Defer full production-readiness scores unless clearly warranted. "
                        "Return FindingReport JSON."
                    ),
                )
            )
        return items
    raise ValueError(f"Unknown mode: {mode}")
