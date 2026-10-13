"""Line checks for JavaScript, Go, and Rust. Stdlib only, no tree-sitter."""

from __future__ import annotations

import re

OTHER_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs"})
_JS = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})

_SECRET_WORDS = frozenset(
    {"password", "passwd", "secret", "token", "apikey", "authorization", "pan", "cvv", "ssn"}
)
_TOKEN_NOISE = frozenset({"count", "name", "type", "id", "list", "index"})

_JS_LOG = re.compile(
    r"\b(?:console|logger|log)\.(?:log|info|warn|warning|error|debug|trace)\s*\("
)
_GO_LOG = re.compile(r"\blog\.(?:Print|Printf|Println|Fatal|Fatalf|Panic|Panicf)\s*\(")
_RUST_LOG = re.compile(r"\b(?:info|warn|error|debug|trace|println|eprintln)!\s*\(")
_JS_CATCH = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{([^{}]*)\}")
_GO_ERR = re.compile(r"if\s+err\s*!=\s*nil\s*\{([^{}]*)\}")
_IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_FN_NAME = re.compile(r"\b(?:function|func|fn)\s+([A-Za-z_][A-Za-z0-9_]*)")


def name_is_secret(name: str) -> bool:
    """True when a name's snake or camel segments name a credential."""
    parts = _segments(name)
    if "api" in parts and "key" in parts:
        return True
    for part in parts:
        if part == "token" and any(other in _TOKEN_NOISE for other in parts):
            continue
        if part in _SECRET_WORDS:
            return True
    return False


def _segments(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return [part.lower() for part in spaced.split("_") if part]


def _mask_literals(line: str) -> str:
    line = re.sub(r"//.*", "", line)
    line = re.sub(r"/\*.*?\*/", "", line)
    line = re.sub(r"`(?:\\.|[^`])*`", '""', line)
    line = re.sub(r'"(?:\\.|[^"\\])*"', '""', line)
    line = re.sub(r"'(?:\\.|[^'\\])*'", "''", line)
    return line


def _is_log_line(line: str, suffix: str) -> bool:
    if suffix in _JS:
        return _JS_LOG.search(line) is not None
    if suffix == ".go":
        return _GO_LOG.search(line) is not None
    if suffix == ".rs":
        return _RUST_LOG.search(line) is not None
    return False


def _is_eager(line: str, suffix: str) -> bool:
    if not _is_log_line(line, suffix):
        return False
    if suffix in _JS:
        return "`" in line or " + " in line
    if suffix == ".go":
        return "fmt.Sprintf" in line
    if suffix == ".rs":
        return "format!" in line
    return False


def _secret_on_line(line: str) -> str | None:
    masked = _mask_literals(line)
    for ident in _IDENT.findall(masked):
        if name_is_secret(ident):
            return ident
    return None


def _js_swallows(body: str) -> bool:
    text = body.strip()
    if not text or re.fullmatch(r"return\b[^;]*;?", text):
        return True
    logged = re.search(r"\b(?:console|logger|log)\.", text) is not None
    return logged and re.search(r"\.(?:message|toString)\b", text) is not None


def _go_swallows(body: str) -> bool:
    text = body.strip()
    if re.search(r"%\+#?v", text):
        return False
    if "err.Error()" in text:
        return True
    return re.fullmatch(r"return(?:\s+nil)?\s*", text) is not None


def _rust_swallows(body: str) -> bool:
    text = body.strip()
    if not text:
        return True
    return any(mark in text for mark in ("println!", "eprintln!", "info!", "error!", "warn!"))


def _rust_line_swallows(line: str) -> bool:
    if not re.search(r"if\s+let\s+Err\(", line):
        return False
    if "{:?" in line or "{:#" in line:
        return False
    match = re.search(r"\{([^{}]*)\}", _mask_literals(line))
    if match is None:
        return False
    return _rust_swallows(match.group(1))


def logging_hits(text: str, suffix: str, *, is_test: bool) -> list[tuple[str, int, str]]:
    """Return (category, line, detail) for one non-Python source file."""
    hits: list[tuple[str, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _is_eager(line, suffix):
            hits.append(("heuristic.logging_eager", lineno, "formatted before the call"))
        if not is_test and _is_log_line(line, suffix):
            secret = _secret_on_line(line)
            if secret:
                hits.append(("heuristic.logging_secret", lineno, secret))
        if is_test:
            continue
        if suffix in _JS:
            for match in _JS_CATCH.finditer(line):
                if _js_swallows(match.group(1)):
                    hits.append(("heuristic.swallowed_exception", lineno, "catch"))
        elif suffix == ".go":
            for match in _GO_ERR.finditer(line):
                if _go_swallows(match.group(1)):
                    hits.append(("heuristic.swallowed_exception", lineno, "err"))
        elif suffix == ".rs" and _rust_line_swallows(line):
            hits.append(("heuristic.swallowed_exception", lineno, "Err"))
    return hits


def _param_count(param_src: str) -> int:
    text = param_src.strip()
    if not text:
        return 0
    return len([part for part in text.split(",") if part.strip()])


def _signature_params(line: str, suffix: str) -> str | None:
    if suffix in _JS and "function" not in line and "=>" not in line:
        return None
    if suffix == ".go" and not line.lstrip().startswith("func "):
        return None
    if suffix == ".rs" and "fn " not in line:
        return None
    match = re.search(r"\(([^)]*)\)", line)
    if match is None:
        return None
    return match.group(1)


def parameter_hits(text: str, suffix: str) -> list[tuple[int, str, int]]:
    """Return (line, function name, parameter count) for lists of 7 or more."""
    hits: list[tuple[int, str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        params = _signature_params(line, suffix)
        if params is None:
            continue
        count = _param_count(params)
        if count < 7:
            continue
        name_match = _FN_NAME.search(line)
        name = name_match.group(1) if name_match else "function"
        hits.append((lineno, name, count))
    return hits


def _is_fn_start(line: str, suffix: str) -> bool:
    if suffix in _JS:
        return "function " in line or "function(" in line or "=>" in line
    if suffix == ".go":
        return line.lstrip().startswith("func ")
    if suffix == ".rs":
        return bool(re.search(r"\bfn\s+", line))
    return False


def function_spans(lines: list[str], suffix: str) -> list[tuple[int, int]]:
    """Inclusive 0-based line ranges for brace-delimited functions."""
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        if not _is_fn_start(lines[index], suffix):
            index += 1
            continue
        depth = 0
        seen = False
        end = index
        closed = False
        while end < len(lines):
            depth += lines[end].count("{") - lines[end].count("}")
            if "{" in lines[end]:
                seen = True
            if seen and depth <= 0:
                spans.append((index, end))
                index = end + 1
                closed = True
                break
            end += 1
        if not closed:
            index += 1
    return spans


def _numbers_in_span(lines: list[str], start: int, end: int) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for offset, line in enumerate(lines[start : end + 1], start=start):
        masked = _mask_literals(line)
        for match in _NUMBER.finditer(masked):
            raw = match.group(0)
            try:
                value = float(raw) if "." in raw else int(raw)
            except ValueError:
                continue
            if value in (-1, 0, 1):
                continue
            found.append((offset + 1, raw))
    return found


def magic_hits(text: str, suffix: str) -> list[tuple[int, str]]:
    """Return (line, literal) for a numeric literal repeated in one function."""
    lines = text.splitlines()
    hits: list[tuple[int, str]] = []
    for start, end in function_spans(lines, suffix):
        counts: dict[str, list[int]] = {}
        for lineno, raw in _numbers_in_span(lines, start, end):
            counts.setdefault(raw, []).append(lineno)
        for raw, places in counts.items():
            if len(places) >= 2:
                hits.append((places[0], raw))
    return hits


def _bool_names(signature: str, suffix: str) -> list[str]:
    match = re.search(r"\(([^)]*)\)", signature)
    if match is None:
        return []
    names: list[str] = []
    for part in match.group(1).split(","):
        piece = part.strip()
        if not piece:
            continue
        if suffix == ".go" and re.search(r"\bbool\b", piece):
            names.append(piece.split()[0])
        elif suffix == ".rs" and re.search(r":\s*bool\b", piece):
            names.append(piece.split(":", 1)[0].strip())
        elif suffix in _JS and (
            re.search(r":\s*boolean\b", piece) or re.search(r"=\s*(?:true|false)\b", piece)
        ):
            names.append(re.split(r"[:?=]", piece, maxsplit=1)[0].strip())
    return [name for name in names if name.isidentifier()]


def boolean_hits(text: str, suffix: str) -> list[tuple[int, str]]:
    """Return (line, parameter) when a bool parameter selects a branch."""
    lines = text.splitlines()
    hits: list[tuple[int, str]] = []
    for start, end in function_spans(lines, suffix):
        signature = lines[start]
        body = "\n".join(_mask_literals(line) for line in lines[start : end + 1])
        for name in _bool_names(signature, suffix):
            if re.search(rf"\bif\s*\(?\s*!?\s*{re.escape(name)}\b", body):
                hits.append((start + 1, name))
    return hits
