"""Grounded single-file fix from a finding ``codeExample`` (no multi-file self-heal)."""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from repolens.schema import Issue

_MULTI_FILE_RE = re.compile(
    r"(?:also\s+edit|and\s+(?:then\s+)?(?:update|change)|files?:)\s+"
    r"[`'\"]?[\w./\\-]+\.py[`'\"]?\s+and\s+[`'\"]?[\w./\\-]+\.py",
    re.IGNORECASE,
)
_PATH_PAIR_RE = re.compile(
    r"([\w./\\-]+\.py)\s+and\s+([\w./\\-]+\.py)",
    re.IGNORECASE,
)
_BEFORE_AFTER_RE = re.compile(
    r"(?is)#\s*Before\b[^\n]*\n(?P<before>.*?)\n#\s*After\b[^\n]*\n(?P<after>.*)$"
)
_FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


class FixRefuseError(ValueError):
    """Finding is not grounded enough for an automatic single-file patch."""


@dataclass(frozen=True)
class FixPlan:
    relative_path: str
    absolute_path: Path
    old_text: str
    new_text: str
    before_snippet: str
    after_snippet: str


def _strip_example(code: str) -> str:
    text = code.strip()
    fences = _FENCE_RE.findall(text)
    if fences:
        # Prefer the largest fenced block (usually the full before/after demo).
        text = max(fences, key=len).strip()
    return text


def _extract_before_after(code: str) -> tuple[str, str]:
    text = _strip_example(code)
    match = _BEFORE_AFTER_RE.search(text)
    if match:
        before = match.group("before").strip() + "\n"
        after = match.group("after").strip() + "\n"
        if before.strip() and after.strip():
            return before, after
    raise FixRefuseError(
        "codeExample is not grounded enough: need a clear `# Before` / `# After` "
        "pair (single file). Copy the remediation by hand or improve the example."
    )


def _refuse_multi_file(code: str) -> None:
    if _MULTI_FILE_RE.search(code) or (
        len(_PATH_PAIR_RE.findall(code)) >= 1 and "Also edit" in code
    ):
        raise FixRefuseError(
            "Hard refuse: multi-file remediation hints detected. "
            "`repolens fix` applies one grounded file only — no autonomous "
            "self-heal loops. Split findings or edit manually."
        )
    # Explicit "Also edit a.py and b.py"
    if re.search(r"Also edit\s+\S+\.py\s+and\s+\S+\.py", code, re.IGNORECASE):
        raise FixRefuseError(
            "Hard refuse: multi-file remediation. Single-file patches only."
        )


def plan_fix(project_root: Path, issue: Issue) -> FixPlan:
    """Build a single-file replacement plan or refuse."""
    root = project_root.resolve()
    example = (issue.codeExample or "").strip()
    if not example:
        raise FixRefuseError(
            "No grounded codeExample on this finding — cannot build a patch."
        )
    _refuse_multi_file(example)

    rel = issue.file.replace("\\", "/").lstrip("./")
    if not rel or ".." in Path(rel).parts:
        raise FixRefuseError(f"Refusing unsafe file path: {issue.file!r}")
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise FixRefuseError(f"Refusing path outside project: {issue.file}") from exc
    if not path.is_file():
        raise FixRefuseError(f"Finding file not found on disk: {rel}")

    before, after = _extract_before_after(example)
    old_text = path.read_text(encoding="utf-8")
    # Match with flexible indent: try exact first, then stripped lines as block.
    if before in old_text:
        new_text = old_text.replace(before, after, 1)
    else:
        new_text = _replace_loose(old_text, before, after)
    if new_text == old_text:
        raise FixRefuseError(
            "Before snippet not found in the file — example may be stale. "
            "Re-run review or apply the recommendedFix manually."
        )
    return FixPlan(
        relative_path=rel,
        absolute_path=path,
        old_text=old_text,
        new_text=new_text,
        before_snippet=before,
        after_snippet=after,
    )


def _replace_loose(old_text: str, before: str, after: str) -> str:
    """Indent-tolerant block replace using normalized line lists."""
    old_lines = old_text.splitlines(keepends=True)
    before_lines = [ln.rstrip("\n") for ln in before.splitlines()]
    after_lines = [ln.rstrip("\n") for ln in after.splitlines()]
    if not before_lines:
        return old_text
    needle = [ln.strip() for ln in before_lines]
    for i in range(len(old_lines) - len(needle) + 1):
        window = [old_lines[i + j].strip() for j in range(len(needle))]
        if window != needle:
            continue
        base_m = re.match(r"^[ \t]*", old_lines[i])
        base_prefix = base_m.group(0) if base_m else ""
        # Relative indent inside the After snippet (vs its first line).
        after0_m = re.match(r"^[ \t]*", after_lines[0]) if after_lines else None
        after0_indent = after0_m.group(0) if after0_m else ""
        rebuilt: list[str] = []
        for line in after_lines:
            line_m = re.match(r"^[ \t]*", line)
            line_indent = line_m.group(0) if line_m else ""
            rel = line_indent[len(after0_indent) :] if line_indent.startswith(
                after0_indent
            ) else line_indent
            rebuilt.append(base_prefix + rel + line.lstrip() + "\n")
        return "".join(old_lines[:i] + rebuilt + old_lines[i + len(needle) :])
    return old_text


def build_unified_diff(plan: FixPlan) -> str:
    old = plan.old_text.splitlines(keepends=True)
    new = plan.new_text.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old,
            new,
            fromfile=f"a/{plan.relative_path}",
            tofile=f"b/{plan.relative_path}",
        )
    )


def syntax_check(path: Path, text: str) -> None:
    """Post-apply check when language tooling allows (Python via ast.parse)."""
    if path.suffix.lower() != ".py":
        return
    try:
        ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise FixRefuseError(
            f"Post-apply Python syntax check failed: {exc}. Patch not applied."
        ) from exc


def apply_fix(plan: FixPlan, *, check_syntax: bool = True) -> None:
    if check_syntax:
        syntax_check(plan.absolute_path, plan.new_text)
    plan.absolute_path.write_text(plan.new_text, encoding="utf-8")
