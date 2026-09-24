"""Near-clone detection (Fast Brain — line/hash only, no AST)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from repolens.heuristics.mega_files import is_mega_file_excluded
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

CODE_SUFFIXES = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".kt"}

DEFAULT_NEAR_CLONE_EXCLUDE_GLOBS: tuple[str, ...] = (
    "**/migrations/**",
    "**/*_pb2.py",
    "**/generated/**",
)


@dataclass(frozen=True)
class PairHit:
    """Matching window between two files (physical line ranges, inclusive)."""

    file_a: str
    file_b: str
    phys_start_a: int
    phys_end_a: int
    phys_start_b: int
    phys_end_b: int


@dataclass(frozen=True)
class CloneBlock:
    """Coalesced near-clone region for one file pair."""

    file_a: str
    file_b: str
    phys_start_a: int
    phys_end_a: int
    phys_start_b: int
    phys_end_b: int
    occurrences: int


@dataclass(frozen=True)
class WindowHit:
    """One sliding-window content hash with physical and normalised line bounds."""

    hash: str
    phys_start: int
    phys_end: int
    norm_start: int
    norm_end: int


def normalize_lines(text: str) -> tuple[list[str], list[int]]:
    """Drop blank lines; map each kept line to its 1-based physical line number."""
    norm: list[str] = []
    phys: list[int] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        norm.append(raw.lstrip())
        phys.append(i)
    return norm, phys


def window_hash(lines: Sequence[str]) -> str:
    """Stable truncated SHA-256 of normalised window text."""
    payload = "\n".join(lines).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def iter_windows(
    norm: list[str],
    phys: list[int],
    *,
    window: int,
    stride: int,
) -> Iterator[WindowHit]:
    """Yield sliding windows over normalised lines with physical line bounds."""
    if len(norm) != len(phys):
        msg = "norm and phys must have the same length"
        raise ValueError(msg)
    if window <= 0 or stride <= 0:
        msg = "window and stride must be positive"
        raise ValueError(msg)
    if len(norm) < window:
        return
    for start in range(0, len(norm) - window + 1, stride):
        end = start + window
        chunk = norm[start:end]
        yield WindowHit(
            hash=window_hash(chunk),
            phys_start=phys[start],
            phys_end=phys[end - 1],
            norm_start=start,
            norm_end=end,
        )


def _pair_offset(hit: PairHit) -> int:
    return hit.phys_start_b - hit.phys_start_a


def _can_merge_pair_hits(cur: PairHit, nxt: PairHit) -> bool:
    if cur.file_a != nxt.file_a or cur.file_b != nxt.file_b:
        return False
    if nxt.phys_start_a > cur.phys_end_a + 1:
        return False
    if nxt.phys_start_b > cur.phys_end_b + 1:
        return False
    return _pair_offset(cur) == _pair_offset(nxt)


def _merge_pair_hits(cur: PairHit, nxt: PairHit) -> PairHit:
    return PairHit(
        cur.file_a,
        cur.file_b,
        cur.phys_start_a,
        max(cur.phys_end_a, nxt.phys_end_a),
        cur.phys_start_b,
        max(cur.phys_end_b, nxt.phys_end_b),
    )


def coalesce_pair_hits(hits_a_to_b: list[PairHit]) -> list[CloneBlock]:
    """Merge overlapping/abutting windows with the same A→B line offset."""
    if not hits_a_to_b:
        return []

    sorted_hits = sorted(
        hits_a_to_b,
        key=lambda h: (h.file_a, h.file_b, h.phys_start_a, h.phys_start_b),
    )
    merged: list[tuple[PairHit, int]] = []
    cur = sorted_hits[0]
    count = 1

    for nxt in sorted_hits[1:]:
        if _can_merge_pair_hits(cur, nxt):
            cur = _merge_pair_hits(cur, nxt)
            count += 1
        else:
            merged.append((cur, count))
            cur = nxt
            count = 1
    merged.append((cur, count))

    return [
        CloneBlock(
            h.file_a,
            h.file_b,
            h.phys_start_a,
            h.phys_end_a,
            h.phys_start_b,
            h.phys_end_b,
            occurrences,
        )
        for h, occurrences in merged
    ]


@dataclass
class NearClonesConfig:
    """Knobs for near-clone detection (Task 4 will mirror in config.py)."""

    enabled: bool = True
    window_lines: int = 12
    stride: int = 6
    min_occurrences: int = 2
    max_clusters: int = 50
    max_findings: int = 10
    medium_at_occurrences: int = 4
    header_comment_lines: int = 15
    exclude_globs: tuple[str, ...] = ()


@dataclass
class NearCloneResult:
    issues: list[Issue] = field(default_factory=list)
    cluster_count: int = 0
    occurrence_count: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _LocatedHit:
    relative: str
    hit: WindowHit
    norm_chunk: tuple[str, ...]


def _is_comment_line(line: str, suffix: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if suffix in {".py", ".pyi"}:
        return stripped.startswith("#")
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
            or stripped.endswith("*/")
        )
    return stripped.startswith("#") or stripped.startswith("//")


def _is_import_line(line: str, suffix: str) -> bool:
    stripped = line.lstrip()
    if not stripped:
        return True
    if suffix in {".py", ".pyi"}:
        return stripped.startswith("import ") or stripped.startswith("from ")
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return stripped.startswith("import ") or "require(" in stripped
    return False


def _should_skip_window(
    *,
    norm_chunk: Sequence[str],
    phys_start: int,
    phys_end: int,
    raw_lines: Sequence[str],
    suffix: str,
    header_n: int,
) -> bool:
    if phys_end <= header_n:
        phys_text = [
            raw_lines[i - 1]
            for i in range(phys_start, phys_end + 1)
            if 1 <= i <= len(raw_lines)
        ]
        if phys_text and all(_is_comment_line(line, suffix) for line in phys_text):
            return True
    non_blank = [line for line in norm_chunk if line.strip()]
    if non_blank and all(_is_import_line(line, suffix) for line in non_blank):
        return True
    return False


def _exclude_globs_for(config: NearClonesConfig) -> tuple[str, ...]:
    return DEFAULT_NEAR_CLONE_EXCLUDE_GLOBS + tuple(config.exclude_globs)


def _block_sort_key(block: CloneBlock) -> tuple[int, int, str]:
    span = block.phys_end_a - block.phys_start_a
    return (-block.occurrences, -span, block.file_a)


def _issue_for_block(block: CloneBlock, *, config: NearClonesConfig) -> Issue:
    span_a = block.phys_end_a - block.phys_start_a + 1
    severity = Severity.LOW
    if block.occurrences >= config.medium_at_occurrences or span_a >= config.window_lines * 2:
        severity = Severity.MEDIUM
    return Issue(
        severity=severity,
        priority="P3",
        category="quality.near_clone",
        file=block.file_a,
        line=block.phys_start_a,
        title=f"Near-clone block: {block.file_a} ↔ {block.file_b}",
        explanation=(
            f"Similar {span_a}-line block also in {block.file_b} "
            f"(lines {block.phys_start_b}–{block.phys_end_b}); "
            f"{block.occurrences} overlapping window match(es)."
        ),
        recommendedFix=(
            "Extract a shared helper/module for the duplicated logic, or document "
            "why intentional duplication is acceptable."
        ),
        fixTiming="if time permits",
        source="heuristic",
    )


def find_near_clones(
    entries: list[FileEntry],
    *,
    config: NearClonesConfig | None = None,
) -> NearCloneResult:
    """Detect duplicate line windows across files; suppress boilerplate; dual-cap output."""
    cfg = config or NearClonesConfig()
    if not cfg.enabled:
        return NearCloneResult()

    excludes = _exclude_globs_for(cfg)
    by_hash: dict[str, list[_LocatedHit]] = {}

    for entry in entries:
        if not entry.path.is_file():
            continue
        suffix = Path(entry.relative).suffix.lower()
        if suffix not in CODE_SUFFIXES:
            continue
        if is_mega_file_excluded(entry.relative, excludes):
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        raw_lines = text.splitlines()
        norm, phys = normalize_lines(text)
        for hit in iter_windows(
            norm, phys, window=cfg.window_lines, stride=cfg.stride
        ):
            chunk = tuple(norm[hit.norm_start : hit.norm_end])
            if _should_skip_window(
                norm_chunk=chunk,
                phys_start=hit.phys_start,
                phys_end=hit.phys_end,
                raw_lines=raw_lines,
                suffix=suffix,
                header_n=cfg.header_comment_lines,
            ):
                continue
            by_hash.setdefault(hit.hash, []).append(
                _LocatedHit(entry.relative, hit, chunk)
            )

    pair_hits: list[PairHit] = []
    for locations in by_hash.values():
        files = {loc.relative for loc in locations}
        if len(files) < cfg.min_occurrences:
            continue
        for i, loc_a in enumerate(locations):
            for loc_b in locations[i + 1 :]:
                if loc_a.relative == loc_b.relative:
                    continue
                fa, fb = loc_a.relative, loc_b.relative
                ha, hb = loc_a.hit, loc_b.hit
                if fa > fb:
                    fa, fb = fb, fa
                    ha, hb = hb, ha
                pair_hits.append(
                    PairHit(
                        fa,
                        fb,
                        ha.phys_start,
                        ha.phys_end,
                        hb.phys_start,
                        hb.phys_end,
                    )
                )

    blocks_by_pair: dict[tuple[str, str], list[PairHit]] = {}
    for ph in pair_hits:
        blocks_by_pair.setdefault((ph.file_a, ph.file_b), []).append(ph)

    all_blocks: list[CloneBlock] = []
    for hits in blocks_by_pair.values():
        all_blocks.extend(coalesce_pair_hits(hits))

    all_blocks.sort(key=_block_sort_key)

    capped_clusters = all_blocks[: cfg.max_clusters]
    cluster_count = len(capped_clusters)
    occurrence_count = sum(b.occurrences for b in capped_clusters)

    top_for_findings = all_blocks[: cfg.max_findings]
    issues = [_issue_for_block(b, config=cfg) for b in top_for_findings]

    notes: list[str] = []
    omitted = len(all_blocks) - len(top_for_findings)
    if omitted > 0:
        notes.append(f"{omitted} additional clone clusters omitted from findings")

    return NearCloneResult(
        issues=issues,
        cluster_count=cluster_count,
        occurrence_count=occurrence_count,
        notes=notes,
    )
