"""Load review playbooks from package data or repository checkout."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def playbooks_dir() -> Path:
    """Return directory containing security.md / architecture.md."""
    # Prefer packaged data
    try:
        root = resources.files("repolens") / "playbooks"
        if root.is_dir() and (root / "security.md").is_file():  # type: ignore[operator]
            return Path(str(root))
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass

    here = Path(__file__).resolve()
    candidates = [
        here.parent / "playbooks",
        here.parents[2] / "playbooks",  # repo root when running from src layout
    ]
    for candidate in candidates:
        if (candidate / "security.md").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate playbooks/security.md. Ensure RepoLens is installed with package data."
    )


def load_playbook(name: str) -> str:
    path = playbooks_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"Playbook not found: {path}")
    return path.read_text(encoding="utf-8")


def playbooks_for_mode(mode: str, *, full_audit: bool = False) -> list[tuple[str, str]]:
    """Return ordered (label, content) playbooks for a CLI mode."""
    if mode == "sentinel":
        return [("P1 security", load_playbook("security.md"))]
    if mode == "architecture":
        return [("P3 architecture", load_playbook("architecture.md"))]
    if mode == "review":
        items = [
            ("P1 security", load_playbook("security.md")),
            (
                "P2 reliability",
                (
                    "Identify high-confidence bugs, reliability, and performance issues "
                    "in the provided files. Require impact and codeExample for Critical/High. "
                    "Return the RepoLens FindingReport JSON schema only."
                ),
            ),
        ]
        if full_audit:
            items.append(("P3 architecture", load_playbook("architecture.md")))
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
