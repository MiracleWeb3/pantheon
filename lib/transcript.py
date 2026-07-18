#!/usr/bin/env python3
"""pantheon transcript reader — what actually happened this turn?

Claude Code writes an append-only JSONL transcript. Hooks get its path and
can reconstruct the current turn: files edited, commands run, tests failed,
skills invoked, tokens spent. This is what makes the verification gate and
receipts REAL instead of honor-system.

Reading strategy: tail-read (4 MB → 32 MB → whole file) until the last real
user prompt is inside the window — turns are almost always small, so the
common case reads one small tail.

stdlib only. Self-check: python3 transcript.py --selftest
"""
import os, json, re

CTX_WINDOW = 200_000  # mainline context budget, tokens

# Flag-form checks live in their own branch with NO leading \b. `--selftest`
# used to sit inside the \b(...)\b group, where it was DEAD: a word boundary
# can never hold between the space and the '-', so `python3 x.py --selftest`
# never registered. That blinded the gate on every stdlib-only project (this
# one included) — both to "verification ran" and to "the check failed".
_RUNNERS = (r"pytest|py_compile|unittest|jest|vitest|mocha|go test|cargo (test|check)|"
            r"npm (test|run test\w*)|yarn test|pnpm test|node --check|tsc|make (test|check)|"
            r"rspec|phpunit|mix test|dotnet test|gradle test|mvn test")
_BUILDERS = (r"npm run build|yarn build|pnpm build|cargo build|go build|go vet|ruff|"
             r"eslint|flake8|pylint|mypy|shellcheck|gcc|g\+\+|javac|swift build")
_FLAGS = r"--selftest|--self-test"
TEST_RE = re.compile(rf"\b(?:{_RUNNERS})\b|(?:{_FLAGS})\b")
VERIFY_RE = re.compile(rf"\b(?:{_RUNNERS}|{_BUILDERS})\b|(?:{_FLAGS})\b")
FAIL_RE = re.compile(
    r"\b[1-9]\d* (failed|errors?)\b|FAILED|Traceback \(most recent|AssertionError|"
    r"npm ERR!|error TS\d|Exit code [1-9]|✗|\bFAIL\b")

CODE_EXT = {"py", "js", "jsx", "ts", "tsx", "go", "rs", "java", "rb", "php", "c", "h",
            "cc", "cpp", "hpp", "cs", "swift", "kt", "scala", "sh", "bash", "zsh",
            "vue", "svelte", "sql"}

STUB_PATTERNS = [
    (re.compile(r"\bTODO\b|\bFIXME\b|\bXXX\b"), "TODO/FIXME"),
    (re.compile(r"\.skip\(|\.only\(|\bxit\(|\bxdescribe\(|@pytest\.mark\.skip"), "skipped/only test"),
    # NOTE: no bare 'placeholder' — it false-positives on the HTML/JSX attribute
    (re.compile(r"NotImplementedError|not implemented", re.I), "unimplemented stub"),
]

# command segments that merely mention a test tool without running one
NOT_A_TEST_RE = re.compile(
    r"^\s*(which|command -v|type|grep|rg|cat|echo|find|ls|man|head|tail|"
    r"pip3? install|pipx|npm i(nstall)?|pnpm (add|i)|yarn add|apt(-get)?|brew)\b")


def _cmd_segments(cmd: str):
    """Split a shell command on && ; | so `pip install x && pytest -q` is judged
    per segment — the installer prefix must not hide (or fake) the test run.

    A heredoc BODY is data, not commands: `python3 - <<'PY' … --selftest … PY`
    is a script that MENTIONS a check, not a check being run. Judging the body
    would count arbitrary inline scripts as verification, and a traceback in
    their output as a failing check — so cut everything from the heredoc on."""
    cmd = re.split(r"<<-?\s*['\"]?\w+", cmd or "", maxsplit=1)[0]
    return [s.strip() for s in re.split(r"&&|\|\||;|\|", cmd) if s.strip()]


def _runs_matching(cmd: str, rx) -> bool:
    return any(rx.search(s) for s in _cmd_segments(cmd) if not NOT_A_TEST_RE.search(s))


def is_code_file(path: str) -> bool:
    p = (path or "").replace("\\", "/")
    if "/docs/" in p or "/node_modules/" in p:
        return False
    return p.rsplit(".", 1)[-1].lower() in CODE_EXT if "." in p else False


def _parse(line):
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _content(obj):
    c = (obj.get("message") or {}).get("content")
    return c if c is not None else obj.get("content")


# anchored: these are machine entries only when they ARE the message, not when
# a real user quotes them mid-prompt
MACHINE_USER_RE = re.compile(
    r"^\s*(This session is being continued from a previous conversation|"
    r"<command-name>|<local-command-|<task-notification|<system-reminder|"
    r"\[Request interrupted)")


def is_real_user(obj) -> bool:
    """A genuine user prompt: user-typed text — not a tool_result carrier, and
    not machine-generated user-typed entries (compact summaries, local-command
    echoes), which would otherwise poison capture and truncate the turn scan."""
    if not obj or obj.get("type") != "user" or obj.get("isMeta"):
        return False
    c = _content(obj)
    if isinstance(c, str):
        return bool(c.strip()) and not MACHINE_USER_RE.search(c)
    if isinstance(c, list):
        kinds = {p.get("type") for p in c if isinstance(p, dict)}
        if "text" not in kinds or "tool_result" in kinds:
            return False
        return not MACHINE_USER_RE.search(user_text(obj))
    return False


def user_text(obj) -> str:
    c = _content(obj)
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict)).strip()
    return ""


def _tail_lines(path: str, max_bytes):
    size = os.path.getsize(path)
    start = 0 if (max_bytes is None or size <= max_bytes) else size - max_bytes
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read()
    if start and b"\n" in data:
        data = data.split(b"\n", 1)[1]  # drop the partial first line
    return data.decode("utf-8", "replace").splitlines(), start == 0


def turn_entries(path: str):
    """Entries from the last real user prompt to EOF (the current turn)."""
    if not path or not os.path.isfile(path):
        return []
    for cap in (4_000_000, 32_000_000, None):
        lines, whole = _tail_lines(path, cap)
        entries = [o for o in (_parse(l) for l in lines) if o]
        idx = None
        for i in range(len(entries) - 1, -1, -1):
            if is_real_user(entries[i]):
                idx = i
                break
        if idx is not None:
            return entries[idx:]
        if whole:
            return entries
    return []


def scan_turn(path: str) -> dict:
    """Digest of the current turn:
       last_user   the user's prompt text
       edits       [{file, added, new, old}]  (Edit / Write / MultiEdit)
       tests       [{command, failed}]        final status per command
       verified    bool — any test/build/lint command ran
       skills      [names] Skill-tool invocations
       out_tokens  assistant output tokens spent this turn"""
    entries = turn_entries(path)
    edits, skills, bash = [], [], {}
    out_tokens = 0
    last_user = ""
    seen_msg_ids = set()
    for obj in entries:
        if is_real_user(obj):
            last_user = user_text(obj) or last_user
        t = obj.get("type")
        c = _content(obj)
        if t == "assistant":
            msg = obj.get("message") or {}
            u = msg.get("usage") or {}
            mid = msg.get("id")
            # Claude Code writes one JSONL line per content block, each carrying
            # the SAME usage — count each message id once or tokens inflate 2-5x
            if not mid or mid not in seen_msg_ids:
                out_tokens += u.get("output_tokens", 0) or 0
                if mid:
                    seen_msg_ids.add(mid)
            if not isinstance(c, list):
                continue
            for p in c:
                if not isinstance(p, dict) or p.get("type") != "tool_use":
                    continue
                name, inp = p.get("name", ""), p.get("input") or {}
                if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                    new = inp.get("new_string") or inp.get("content") or inp.get("new_source") or ""
                    old = inp.get("old_string") or ""
                    if name == "MultiEdit":
                        eds = inp.get("edits") or []
                        new = "\n".join(e.get("new_string", "") for e in eds)
                        old = "\n".join(e.get("old_string", "") for e in eds)
                    edits.append({"file": inp.get("file_path") or inp.get("notebook_path", ""),
                                  "added": new.count("\n") + 1 if new else 0,
                                  "removed": old.count("\n") + 1 if old else 0,
                                  "new": new, "old": old})
                elif name == "Bash":
                    bash[p.get("id")] = {"command": inp.get("command", ""), "failed": False,
                                         "seen_result": False}
                elif name == "Skill":
                    skills.append(str(inp.get("skill", "")))
        elif t == "user" and isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get("type") == "tool_result":
                    rec = bash.get(p.get("tool_use_id"))
                    if rec is None:
                        continue
                    body = p.get("content")
                    if isinstance(body, list):
                        body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
                    body = body if isinstance(body, str) else ""
                    rec["seen_result"] = True
                    rec["failed"] = bool(p.get("is_error")) or bool(FAIL_RE.search(body[-4000:]))
    # final verdict per check command (a later re-run overrides an earlier
    # fail); judged per shell segment: `which pytest` doesn't count, but the
    # pytest in `pip install -e . && pytest -q` does. Tests and build/lint
    # commands are tracked alike — a FAILING build is not verification, it's
    # a failing check.
    tests, final = [], {}
    for rec in bash.values():
        cmd = rec["command"]
        if not rec["seen_result"]:
            continue
        if _runs_matching(cmd, TEST_RE) or _runs_matching(cmd, VERIFY_RE):
            final[cmd.strip()[:60]] = rec["failed"]
    for cmd, failed in final.items():
        tests.append({"command": cmd, "failed": failed})
    verified = any(not f for f in final.values())
    return {"last_user": last_user, "edits": edits, "tests": tests,
            "verified": verified, "skills": skills, "out_tokens": out_tokens}


# unambiguous stubs — never a legitimate part of "done" new code
STRONG_STUB_PATTERNS = [
    (re.compile(r"\.skip\(|\.only\(|\bxit\(|\bxdescribe\(|@pytest\.mark\.skip"), "skipped/only test"),
    (re.compile(r"NotImplementedError|not implemented", re.I), "unimplemented stub"),
]


def introduced_stubs(edits) -> list:
    """Stub markers introduced this turn, code files only. Edits are diffed
    new-vs-old; full-file Writes have no old baseline, so only the STRONG
    patterns apply there (a pre-existing TODO in a rewritten file is not
    'introduced', but a fresh NotImplementedError scaffold is). Returns
    ['file: kind', ...]."""
    found = []
    for e in edits:
        if not is_code_file(e.get("file", "")):
            continue
        old = e.get("old") or ""
        patterns = STUB_PATTERNS if old else STRONG_STUB_PATTERNS
        for rx, kind in patterns:
            if len(rx.findall(e.get("new") or "")) > len(rx.findall(old)):
                found.append(f"{os.path.basename(e['file'])}: {kind}")
    return sorted(set(found))


def context_pct(path: str) -> int:
    """% of the context window filled, from the LAST usage record's input side.
    (Transcript size is meaningless — it's append-only.) -1 when unknown."""
    try:
        lines, _ = _tail_lines(path, 512_000)
        for ln in reversed(lines):
            if '"usage"' not in ln:
                continue
            obj = _parse(ln)
            if not obj:
                continue
            u = (obj.get("message") or {}).get("usage") or obj.get("usage")
            if isinstance(u, dict):
                tokens = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                          + u.get("cache_creation_input_tokens", 0))
                if tokens > 0:
                    return min(100, int(tokens / CTX_WINDOW * 100))
        return -1
    except Exception:
        return -1


def selftest() -> int:
    import tempfile
    d = tempfile.mkdtemp(prefix="pantheon-tr-")
    p = os.path.join(d, "t.jsonl")
    rows = [
        {"type": "user", "message": {"content": "old turn, ignore me"}},
        {"type": "assistant", "message": {"content": [], "usage": {"output_tokens": 99}}},
        {"type": "user", "message": {"content": "fix the parser and run tests"}},
        # same message split across two JSONL lines (one per block) — usage
        # repeats on both; it must be counted ONCE
        {"type": "assistant", "message": {"id": "m1", "usage": {"output_tokens": 50,
            "input_tokens": 100_000, "cache_read_input_tokens": 0},
            "content": [{"type": "text", "text": "on it"}]}},
        {"type": "assistant", "message": {"id": "m1", "usage": {"output_tokens": 50,
            "input_tokens": 100_000, "cache_read_input_tokens": 0},
            "content": [
              {"type": "tool_use", "id": "t1", "name": "Edit",
               "input": {"file_path": "/x/app.py", "old_string": "a=1",
                         "new_string": "a=2  # TODO handle zero"}},
              {"type": "tool_use", "id": "t2", "name": "Bash",
               "input": {"command": "pytest -q tests/"}},
              {"type": "tool_use", "id": "t3", "name": "Skill",
               "input": {"skill": "pantheon:hydra"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t2", "is_error": False,
             "content": [{"type": "text", "text": "2 passed, 1 failed"}]}]}},
    ]
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows) + "\n")
    t = scan_turn(p)
    assert t["last_user"].startswith("fix the parser")
    assert t["out_tokens"] == 50, t["out_tokens"]          # old turn's 99 excluded
    assert t["edits"] and t["edits"][0]["file"] == "/x/app.py"
    assert t["edits"][0]["removed"] == 1  # old_string "a=1" is one replaced line
    assert t["tests"] == [{"command": "pytest -q tests/", "failed": True}]
    assert not t["verified"]  # the only check FAILED — that is not verification
    assert t["skills"] == ["pantheon:hydra"]
    assert introduced_stubs(t["edits"]) == ["app.py: TODO/FIXME"]
    # a re-run that passes overrides the earlier fail
    rows.append({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t4", "name": "Bash",
         "input": {"command": "pytest -q tests/"}}]}})
    rows.append({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t4", "content": "3 passed"}]}})
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows) + "\n")
    t2 = scan_turn(p)
    assert t2["tests"] == [{"command": "pytest -q tests/", "failed": False}], t2["tests"]
    assert t2["verified"]  # a passing re-run restores verification
    # a failing BUILD is a failing check, not verification
    rows2 = [
        {"type": "user", "message": {"content": "wire up the export module"}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "b9", "name": "Bash",
             "input": {"command": "npm run build"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "b9", "is_error": True,
             "content": "error TS2304: Cannot find name"}]}},
    ]
    p2 = os.path.join(d, "t2.jsonl")
    with open(p2, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows2) + "\n")
    tb = scan_turn(p2)
    assert not tb["verified"] and tb["tests"] == [{"command": "npm run build", "failed": True}]
    assert 45 <= context_pct(p) <= 55                       # 100k of 200k
    assert context_pct("/nonexistent") == -1
    assert is_code_file("a/b.py") and not is_code_file("a/b.md") and not is_code_file("x")
    assert not FAIL_RE.search("0 failed, 12 passed")
    # gate false-positive/negative regressions (adversarial review + verify pass):
    # 1) full-file Write keeps a pre-existing TODO -> NOT an introduced stub...
    assert introduced_stubs([{"file": "a.py", "new": "x=1  # TODO old note", "old": ""}]) == []
    # ...but a fresh NotImplementedError scaffold via Write IS caught (strong stub)
    assert introduced_stubs([{"file": "h.py", "new": "def f():\n    raise NotImplementedError",
                              "old": ""}]) == ["h.py: unimplemented stub"]
    # 2) HTML placeholder attribute is not an 'unimplemented stub'
    assert introduced_stubs([{"file": "L.tsx", "new": '<input placeholder="Email">',
                              "old": "<input>"}]) == []
    # 3) mentioning a test tool is not running one — but compound commands count
    assert not _runs_matching("which pytest", TEST_RE)
    assert not _runs_matching("pip install pytest", TEST_RE)
    assert not _runs_matching("grep -rn pytest .", TEST_RE)
    assert _runs_matching("pytest -q", TEST_RE)
    assert _runs_matching("pip install -e . && pytest -q", TEST_RE)
    assert _runs_matching("npm install && npm test", VERIFY_RE)
    assert _runs_matching("find . -name 'test_*' | xargs pytest", TEST_RE)
    # REGRESSION: flag-form checks. These sat inside a \b(...) group where the
    # boundary could never hold before '-', so every --selftest run was invisible
    # — the gate nagged for verification that HAD run, and could not see one fail.
    assert _runs_matching("python3 scripts/doctor.py --selftest", TEST_RE)
    assert _runs_matching("python3 lib/store.py --selftest", VERIFY_RE)
    assert _runs_matching("cd lib && python3 store.py --selftest", TEST_RE)
    assert not _runs_matching("grep -rn selftest .", TEST_RE)      # mention ≠ run
    assert not _runs_matching("echo --selftesting", TEST_RE)       # \b still guards the tail
    # a heredoc BODY is data: an inline script that mentions a runner is not a
    # check, and a traceback in its output must not read as a failing check
    assert not _runs_matching("python3 - <<'PY'\nx = 'pytest --selftest'\nPY", TEST_RE)
    assert not _runs_matching("cat <<EOF\nnpm test\nEOF", VERIFY_RE)
    assert _runs_matching("python3 x.py --selftest && cat <<EOF\nnope\nEOF", TEST_RE)
    # 4) machine-generated 'user' entries are not real prompts — but a real user
    # QUOTING those markers mid-prompt still is
    assert not is_real_user({"type": "user", "message": {"content":
        "This session is being continued from a previous conversation. Summary: ..."}})
    assert not is_real_user({"type": "user", "message": {"content":
        "<command-name>/compact</command-name> ran"}})
    assert not is_real_user({"type": "user", "message": {"content":
        "<task-notification>background job finished</task-notification>"}})
    assert is_real_user({"type": "user", "message": {"content": "fix the bug please"}})
    assert is_real_user({"type": "user", "message": {"content":
        "why does <command-name> appear in my transcript? fix the hook"}})
    print("selftest ok — turn scan, stub diff, test verdicts, context%, gate FP/FN guards")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
