"""Match modules to architecture boundary path globs."""

from __future__ import annotations

import fnmatch

from repolens.architecture.schema import Boundary


def module_path_form(module: str) -> str:
    """``packcycle.a`` → ``packcycle/a`` for glob matching."""
    return module.replace(".", "/")


def match_boundary(module: str, boundary: Boundary) -> bool:
    """Return True when *module* belongs to *boundary.path*."""
    pattern = boundary.path.strip()
    if not pattern:
        return False
    dotted = module
    slashed = module_path_form(module)
    forms = (dotted, slashed, f"{slashed}.py")
    for form in forms:
        if fnmatch.fnmatchcase(form, pattern):
            return True

    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        if not prefix:
            return True
        if slashed == prefix or slashed.startswith(prefix + "/"):
            return True
        dotted_prefix = prefix.replace("/", ".")
        if dotted == dotted_prefix or dotted.startswith(dotted_prefix + "."):
            return True

    if pattern.endswith("/*"):
        prefix = pattern[:-2].rstrip("/")
        if slashed.startswith(prefix + "/") and "/" not in slashed[len(prefix) + 1 :]:
            return True

    return False
