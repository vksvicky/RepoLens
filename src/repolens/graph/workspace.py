"""Detect monorepo / workspace manifests and emit inter-package edges (#113).

Honesty: Python ``grimp`` remains the primary module graph. Workspace mode adds
**package-level** edges (pnpm/npm/Cargo/go.work) so cross-service cycles show up
even when languages differ. It does not replace language-specific analysis.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from repolens.graph.types import EdgeKind, GraphResult, GraphStatus, ImportEdge, ImportScope

_PNPM_GLOB_LINE = re.compile(r"""^\s*-\s*['"]?([^'"#\n]+)['"]?""")
_CARGO_MEMBER = re.compile(r"""^\s*['"]([^'"]+)['"]\s*,?\s*$""")
_GO_USE = re.compile(r"""^\s*\./([^\s]+)\s*$""")


@dataclass(frozen=True)
class WorkspaceMember:
    name: str
    path: str  # relative to workspace root
    depends_on: tuple[str, ...] = ()


@dataclass
class WorkspaceManifest:
    kind: str  # pnpm | npm | cargo | go
    root: Path
    members: list[WorkspaceMember] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def detect_workspace(root: Path) -> WorkspaceManifest | None:
    """Return the first recognized workspace manifest under *root*, or None."""
    root = root.resolve()
    for detector in (_detect_pnpm, _detect_npm, _detect_cargo, _detect_go_work):
        found = detector(root)
        if found is not None:
            return found
    return None


def inter_package_edges(ws: WorkspaceManifest) -> list[ImportEdge]:
    """Edges from declared workspace dependencies (package → package)."""
    known = {m.name for m in ws.members}
    edges: list[ImportEdge] = []
    for member in ws.members:
        for dep in member.depends_on:
            if dep in known and dep != member.name:
                edges.append(
                    ImportEdge(
                        importer=member.name,
                        imported=dep,
                        kind=EdgeKind.RUNTIME,
                        scope=ImportScope.MODULE,
                        line=None,
                    )
                )
    return edges


def workspace_graph_result(root: Path) -> GraphResult:
    """GraphResult with only workspace package edges (merge with grimp separately)."""
    ws = detect_workspace(root)
    if ws is None:
        return GraphResult(
            status=GraphStatus.SKIPPED,
            durability_gaps=["workspace: no workspace manifest detected"],
        )
    edges = inter_package_edges(ws)
    gaps = list(ws.notes)
    gaps.append(
        f"workspace.{ws.kind}: {len(ws.members)} member(s); "
        "package-level edges only (complements Python grimp)"
    )
    if not edges:
        return GraphResult(
            status=GraphStatus.PARTIAL if gaps else GraphStatus.OK,
            packages=[m.name for m in ws.members],
            edges=[],
            gated_edges=[],
            durability_gaps=gaps,
        )
    return GraphResult(
        status=GraphStatus.OK,
        packages=[m.name for m in ws.members],
        edges=edges,
        gated_edges=list(edges),
        durability_gaps=gaps,
        module_count=len({e.importer for e in edges} | {e.imported for e in edges}),
    )


# --- detectors -----------------------------------------------------------------


def _expand_glob_members(root: Path, pattern: str) -> list[Path]:
    pat = pattern.strip().strip("'\"")
    if not pat:
        return []
    # pnpm uses packages/* style
    if "*" in pat or "?" in pat:
        return sorted(p for p in root.glob(pat) if p.is_dir())
    candidate = root / pat
    return [candidate] if candidate.is_dir() else []


def _read_package_json(path: Path) -> tuple[str, tuple[str, ...]]:
    pkg = path / "package.json"
    if not pkg.is_file():
        return path.name, ()
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path.name, ()
    name = str(data.get("name") or path.name)
    deps: list[str] = []
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        block = data.get(key) or {}
        if isinstance(block, dict):
            deps.extend(str(k) for k in block)
    return name, tuple(dict.fromkeys(deps))


def _detect_pnpm(root: Path) -> WorkspaceManifest | None:
    manifest = root / "pnpm-workspace.yaml"
    if not manifest.is_file():
        return None
    patterns: list[str] = []
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return None
    in_packages = False
    for line in text.splitlines():
        if line.strip().startswith("packages:"):
            in_packages = True
            continue
        if in_packages:
            if line and not line[0].isspace() and not line.strip().startswith("-"):
                break
            m = _PNPM_GLOB_LINE.match(line)
            if m:
                patterns.append(m.group(1).strip())
    members: list[WorkspaceMember] = []
    for pat in patterns:
        for member_path in _expand_glob_members(root, pat):
            name, deps = _read_package_json(member_path)
            rel = str(member_path.relative_to(root)).replace("\\", "/")
            members.append(WorkspaceMember(name=name, path=rel, depends_on=deps))
    return WorkspaceManifest(kind="pnpm", root=root, members=members)


def _detect_npm(root: Path) -> WorkspaceManifest | None:
    pkg = root / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    workspaces = data.get("workspaces")
    patterns: list[str] = []
    if isinstance(workspaces, list):
        patterns = [str(p) for p in workspaces]
    elif isinstance(workspaces, dict) and isinstance(workspaces.get("packages"), list):
        patterns = [str(p) for p in workspaces["packages"]]
    else:
        return None
    members: list[WorkspaceMember] = []
    for pat in patterns:
        for member_path in _expand_glob_members(root, pat):
            name, deps = _read_package_json(member_path)
            rel = str(member_path.relative_to(root)).replace("\\", "/")
            members.append(WorkspaceMember(name=name, path=rel, depends_on=deps))
    return WorkspaceManifest(kind="npm", root=root, members=members)


def _parse_cargo_toml_name_and_path_deps(text: str) -> tuple[str | None, tuple[str, ...]]:
    name = None
    deps: list[str] = []
    in_package = False
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_package = stripped == "[package]"
            in_deps = stripped == "[dependencies]"
            continue
        if in_package and stripped.startswith("name"):
            m = re.match(r"""name\s*=\s*['"]([^'"]+)['"]""", stripped)
            if m:
                name = m.group(1)
        if in_deps and "=" in stripped and not stripped.startswith("#"):
            dep_name = stripped.split("=", 1)[0].strip().strip("'\"")
            if dep_name and "path" in stripped:
                deps.append(dep_name)
    return name, tuple(deps)


def _detect_cargo(root: Path) -> WorkspaceManifest | None:
    cargo = root / "Cargo.toml"
    if not cargo.is_file():
        return None
    try:
        text = cargo.read_text(encoding="utf-8")
    except OSError:
        return None
    if "[workspace]" not in text:
        return None
    member_globs: list[str] = []
    in_members = False
    for line in text.splitlines():
        if "members" in line and "=" in line and "[" in line:
            # members = ["a", "b"]
            inner = re.findall(r"""['"]([^'"]+)['"]""", line)
            member_globs.extend(inner)
            continue
        if line.strip() == "members = [":
            in_members = True
            continue
        if in_members:
            if line.strip().startswith("]"):
                in_members = False
                continue
            m = _CARGO_MEMBER.match(line)
            if m:
                member_globs.append(m.group(1))
    members: list[WorkspaceMember] = []
    for glob in member_globs:
        for member_path in _expand_glob_members(root, glob):
            ct = member_path / "Cargo.toml"
            if not ct.is_file():
                continue
            try:
                body = ct.read_text(encoding="utf-8")
            except OSError:
                continue
            name, deps = _parse_cargo_toml_name_and_path_deps(body)
            if not name:
                name = member_path.name
            rel = str(member_path.relative_to(root)).replace("\\", "/")
            members.append(WorkspaceMember(name=name, path=rel, depends_on=deps))
    return WorkspaceManifest(kind="cargo", root=root, members=members)


def _detect_go_work(root: Path) -> WorkspaceManifest | None:
    work = root / "go.work"
    if not work.is_file():
        return None
    try:
        text = work.read_text(encoding="utf-8")
    except OSError:
        return None
    members: list[WorkspaceMember] = []
    in_use = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("use ("):
            in_use = True
            continue
        if in_use and stripped == ")":
            in_use = False
            continue
        if stripped.startswith("use "):
            token = stripped[4:].strip().strip("'\"")
            if token.startswith("./"):
                token = token[2:]
            member_path = root / token
            if member_path.is_dir():
                rel = str(member_path.relative_to(root)).replace("\\", "/")
                members.append(WorkspaceMember(name=rel.replace("/", "."), path=rel))
            continue
        if in_use:
            m = _GO_USE.match(line) or re.match(r"""^\s*\./([^\s]+)\s*$""", line)
            if m:
                token = m.group(1)
                member_path = root / token
                if member_path.is_dir():
                    rel = str(member_path.relative_to(root)).replace("\\", "/")
                    members.append(
                        WorkspaceMember(name=rel.replace("/", "."), path=rel)
                    )
    return WorkspaceManifest(kind="go", root=root, members=members)
