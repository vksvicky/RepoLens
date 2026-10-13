"""Tests for logging hygiene heuristics (eager formatting, secrets, swallowed exceptions)."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics.logging_hygiene import find_logging_hygiene
from repolens.inventory import FileEntry
from repolens.schema import Severity


def _entry(tmp_path: Path, rel: str, content: str) -> FileEntry:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return FileEntry(path=path, relative=rel, size=len(content), priority_band=2)


def test_logging_eager_catches_fstrings_and_concat(tmp_path: Path) -> None:
    code = """
import logging
logger = logging.getLogger(__name__)

def do_work(user, item):
    logger.info(f"processing {user}")
    log.debug("item: " + str(item))
    logger.warning("user is %s", user)  # Clean
"""
    entry = _entry(tmp_path, "src/worker.py", code)
    issues = find_logging_hygiene([entry])

    eager = [i for i in issues if i.category == "heuristic.logging_eager"]
    assert len(eager) == 2
    assert eager[0].line == 6
    assert eager[0].priority == "P3"
    assert eager[0].severity == Severity.LOW
    assert "parameterized" in eager[0].explanation.lower() or "%s" in eager[0].explanation
    assert eager[1].line == 7


def test_logging_secret_catches_sensitive_terms_in_log_or_print(tmp_path: Path) -> None:
    code = """
import logging
log = logging.getLogger(__name__)

def auth(password, token, api_key):
    log.info("Auth attempt with password: %s", password)
    print("User token:", token)
    logger.debug(f"API_KEY={api_key}")
    # False positive guards:
    tokenizer = "tokenizer"
    log.info("Tokenizer initialized: %s", tokenizer)
"""
    entry = _entry(tmp_path, "src/auth.py", code)
    issues = find_logging_hygiene([entry])

    secrets = [i for i in issues if i.category == "heuristic.logging_secret"]
    assert len(secrets) == 3
    assert secrets[0].line == 6
    assert secrets[0].priority == "P2"
    assert secrets[0].severity == Severity.MEDIUM
    assert secrets[1].line == 7
    assert secrets[2].line == 8


def test_logging_secret_skips_test_files(tmp_path: Path) -> None:
    code = """
def test_login():
    print("password is test_pass")
"""
    entry = _entry(tmp_path, "tests/test_login.py", code)
    issues = find_logging_hygiene([entry])

    secrets = [i for i in issues if i.category == "heuristic.logging_secret"]
    assert len(secrets) == 0


def test_swallowed_exception_catches_bare_pass_or_return(tmp_path: Path) -> None:
    code = """
def handle():
    try:
        dangerous()
    except Exception:
        pass

    try:
        dangerous()
    except ValueError:
        ...

    try:
        dangerous()
    except KeyError:
        return None

    try:
        dangerous()
    except OSError:
        logger.exception("Failed to read")

    try:
        dangerous()
    except RuntimeError as e:
        log.error("Failed: %s", e, exc_info=True)
"""
    entry = _entry(tmp_path, "src/handler.py", code)
    issues = find_logging_hygiene([entry])

    swallowed = [i for i in issues if i.category == "heuristic.swallowed_exception"]
    assert len(swallowed) == 3
    lines = [s.line for s in swallowed]
    assert 5 in lines or 6 in lines  # except or body line
    assert swallowed[0].priority == "P2"
    assert swallowed[0].severity == Severity.MEDIUM


def test_empty_file_and_syntax_error(tmp_path: Path) -> None:
    e1 = _entry(tmp_path, "src/empty.py", "")
    e2 = _entry(tmp_path, "src/broken.py", "def syntax error !!!")
    issues = find_logging_hygiene([e1, e2])
    assert issues == []


def test_secret_follows_identifiers_not_prose(tmp_path: Path) -> None:
    code = """
import logging
log = logging.getLogger(__name__)

def auth(user_password, access_token):
    log.info("password reset email sent")
    log.info("login %s", user_password)
    logging.getLogger(__name__).info("session %s", access_token)
    log.info("tokenizer ready")
"""
    entry = _entry(tmp_path, "src/auth_ids.py", code)
    issues = find_logging_hygiene([entry])
    secrets = [i for i in issues if i.category == "heuristic.logging_secret"]
    lines = [i.line for i in secrets]
    assert lines == [7, 8]


def test_log_without_traceback_is_swallowed(tmp_path: Path) -> None:
    code = """
def handle():
    try:
        dangerous()
    except OSError as exc:
        logger.error(str(exc))
    try:
        dangerous()
    except OSError as exc:
        logger.exception("read failed")
"""
    entry = _entry(tmp_path, "src/errors.py", code)
    issues = find_logging_hygiene([entry])
    swallowed = [i for i in issues if i.category == "heuristic.swallowed_exception"]
    assert len(swallowed) == 1
    assert swallowed[0].line == 5


def test_js_go_rust_logging(tmp_path: Path) -> None:
    js = """
function run(user_password) {
  console.log(`user ${userId}`);
  console.log("user %s", userId);
  console.log("password reset sent");
  console.log(user_password);
  try { work(); } catch (e) {}
  try { work(); } catch (e) { console.error(e); }
  try { work(); } catch (e) { console.error(e.message); }
}
"""
    go = """
package main
func run(userPassword string) {
    log.Printf("user %s", user)
    log.Print(fmt.Sprintf("user %s", user))
    log.Printf("login %s", userPassword)
    if err != nil { return nil }
    if err != nil { return err }
    if err != nil { log.Printf("%s", err.Error()) }
}
"""
    rust = """
fn run(user_password: String) {
    info!("user {}", user);
    info!(format!("user {}", user));
    info!("login {}", user_password);
    if let Err(_) = work() {}
    if let Err(err) = work() { println!("{}", err); }
    if let Err(err) = work() { println!("{:?}", err); }
}
"""
    files = [
        _entry(tmp_path, "src/run.js", js),
        _entry(tmp_path, "src/run.go", go),
        _entry(tmp_path, "src/run.rs", rust),
    ]
    issues = find_logging_hygiene(files)
    eager = {(i.file, i.line) for i in issues if i.category == "heuristic.logging_eager"}
    secrets = {(i.file, i.line) for i in issues if i.category == "heuristic.logging_secret"}
    swallowed = {(i.file, i.line) for i in issues if i.category == "heuristic.swallowed_exception"}
    assert ("src/run.js", 3) in eager
    assert ("src/run.js", 4) not in eager
    assert ("src/run.go", 5) in eager
    assert ("src/run.go", 4) not in eager
    assert ("src/run.rs", 4) in eager
    assert ("src/run.rs", 3) not in eager
    assert ("src/run.js", 6) in secrets
    assert ("src/run.js", 5) not in secrets
    assert ("src/run.go", 6) in secrets
    assert ("src/run.rs", 5) in secrets
    assert ("src/run.js", 7) in swallowed
    assert ("src/run.js", 9) in swallowed
    assert ("src/run.js", 8) not in swallowed
    assert ("src/run.go", 7) in swallowed
    assert ("src/run.go", 8) not in swallowed
    assert ("src/run.go", 9) in swallowed
    assert ("src/run.rs", 6) in swallowed
    assert ("src/run.rs", 7) in swallowed
    assert ("src/run.rs", 8) not in swallowed
