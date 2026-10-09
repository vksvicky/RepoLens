"""Insecure http:// and weak TLS literals (Fast Brain)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from repolens.heuristics.paths import is_test_source
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".cs",
    ".kt",
    ".java",
}

_HTTP_RE = re.compile(r"http://[^\s'\"<>]+")
_WEAK_VERSION_NEAR = re.compile(
    r"(?:min(?:imum)?[_-]?version|PROTOCOL_TLSv1(?![_23]))[^\n]{0,40}"
    r"(?:TLSv1(?:\.[01])?(?![_23.])|sslv[23])",
    re.IGNORECASE,
)


def _comment_only(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith("//")


def _host_is_schema_or_loopback(host: str) -> bool:
    h = host.lower().strip().strip("[]")
    if h.startswith("www."):
        h = h[4:]
    if h in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return True
    if h.startswith("schemas."):
        return True
    for root in ("w3.org", "xml.org", "json-schema.org"):
        if h == root or h.endswith("." + root):
            return True
    if h == "maven.apache.org" or h.endswith(".maven.apache.org"):
        return True
    return False


def _http_hits(line: str) -> list[str]:
    hits: list[str] = []
    for match in _HTTP_RE.finditer(line):
        raw = match.group(0).rstrip(").,;]")
        try:
            host = urlparse(raw).hostname or ""
        except ValueError:
            # Incomplete IPv6 / regex-like literals (e.g. http://[^\s…) must not abort.
            continue
        if not host:
            continue
        if _host_is_schema_or_loopback(host):
            continue
        hits.append(raw)
    return hits


def _is_regex_detector_line(line: str) -> bool:
    """True for pattern definitions that mention TLS tokens without configuring TLS."""
    stripped = line.strip()
    if "re.compile" in stripped or "re.search" in stripped or "re.match" in stripped:
        return True
    if "(?!" in stripped or "(?:" in stripped:
        return True
    if stripped.startswith("r\"") or stripped.startswith("r'"):
        return True
    # Quoted protocol needles used only for membership/search (detector code).
    if re.search(r"""["']PROTOCOL_SSL""", stripped) and " in " in stripped:
        return True
    return False


def _weak_tls_hit(line: str) -> bool:
    if _is_regex_detector_line(line):
        return False
    if "PROTOCOL_SSLv2" in line or "PROTOCOL_SSLv3" in line:
        return True
    if re.search(r"PROTOCOL_TLSv1(?![_23])", line):
        return True
    if re.search(r"TLSv1\.[01]\b", line):
        return True
    if _WEAK_VERSION_NEAR.search(line) and re.search(r"TLSv1(?![_23.])", line, re.I):
        return True
    return False


def find_transport_tls(files: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []
    for entry in files:
        if not entry.path.is_file():
            continue
        if is_test_source(entry.relative):
            continue
        if entry.path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _comment_only(line):
                continue
            urls = _http_hits(line)
            weak = _weak_tls_hit(line)
            if not urls and not weak:
                continue
            snippet = urls[0] if urls else line.strip()[:80]
            issues.append(
                Issue(
                    severity=Severity.MEDIUM,
                    priority="P1",
                    category="heuristic.transport_tls",
                    file=entry.relative,
                    line=lineno,
                    title="Insecure HTTP or weak TLS setting",
                    explanation=(
                        f"{entry.relative}:{lineno} looks like cleartext HTTP or a "
                        f"legacy TLS version ({snippet}). Loopback and XML/JSON schema "
                        "namespaces are ignored."
                    ),
                    impact=(
                        "Cleartext or obsolete TLS can expose credentials and data "
                        "in transit."
                    ),
                    recommendedFix=(
                        "Use HTTPS, disable SSLv2/SSLv3/TLS 1.0/1.1, and set a modern "
                        "minimum TLS version (1.2+)."
                    ),
                    codeExample=(
                        "# Prefer https:// and TLS 1.2+\n"
                        "# ssl.TLSVersion.TLSv1_2"
                    ),
                    fixTiming="before launch",
                    source="heuristic",
                )
            )
    return issues
