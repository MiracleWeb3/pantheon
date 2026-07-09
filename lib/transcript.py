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

TEST_RE = re.compile(
    r"\b(pytest|py_compile|unittest|jest|vitest|mocha|go test|cargo (test|check)|"
    r"npm (test|run test\w*)|yarn test|pnpm test|node --check|tsc\b|make (test|check)|"
    r"rspec|phpunit|mix test|dotnet test|gradle test|mvn test|--selftest)\b")
VERIFY_RE = re.compile(
    TEST_RE.pattern[:-3] + r"|npm run build|yarn build|pnpm build|cargo build|go build|"
    r"go vet|ruff|eslint|flake8|pylint|mypy|shellcheck|gcc|g\+\+|javac|swift build)\b")
FAIL_RE = re.compile(
    r"\b[1-9]\d* (failed|errors?)\b|FAILED|Traceback \(most recent|AssertionError|"
    r"npm ERR!|error TS\d|Exit code [1-9]|✗|\bFAIL\b")

CODE_EXT = {"py", "js", "jsx", "ts", "tsx", "go", "rs", "java", "rb", "php", "c", "h",
            "cc", "cpp", "hpp", "cs", "swift", "kt", "scala", "sh", "bash", "zsh",
            "vue", "svelte", "sql"}

STUB_PATTERNS = [
    (re.compile(r"\bTODO\b|\bFIXME\b|\bXXX\b"), "TODO/FIXME"),
    (re.compile(r"\.skip\(|\.only\(|\bxit\(|\bxdescribe\(|@pytest\.mark\.skip"), "skipped/only test"),
    (re.compile(r"NotImplementedError|not implemented|\bplaceholder\b", re.I), "unimplemented stub"),
]


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


def is_real_user(obj) -> bool:
    """A genuine user prompt: user-typed text, not a tool_result carrier."""
    if not obj or obj.get("type") != "user" or obj.get("isMeta"):
        return False
    c = _content(obj)
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        kinds = {p.get("type") for p in c if isinstance(p, dict)}
        return "text" in kinds and "tool_result" not in kinds
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
    for obj in entries:
        if is_real_user(obj):
            last_user = user_text(obj) or last_user
        t = obj.get("type")
        c = _content(obj)
        if t == "assistant":
            u = (obj.get("message") or {}).get("usage") or {}
            out_tokens += u.get("output_tokens", 0) or 0
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
    # final verdict per test command (a later re-run overrides an earlier fail)
    tests, final = [], {}
    verified = False
    for rec in bash.values():
        cmd = rec["command"]
        if VERIFY_RE.search(cmd) and rec["seen_result"]:
            verified = True
        if TEST_RE.search(cmd) and rec["seen_result"]:
            final[cmd.strip()[:60]] = rec["failed"]
    for cmd, failed in final.items():
        tests.append({"command": cmd, "failed": failed})
    return {"last_user": last_user, "edits": edits, "tests": tests,
            "verified": verified, "skills": skills, "out_tokens": out_tokens}


def introduced_stubs(edits) -> list:
    """Stub markers present in NEW content but not in the replaced content,
    code files only. Returns ['file: kind', ...]."""
    found = []
    for e in edits:
        if not is_code_file(e.get("file", "")):
            continue
        for rx, kind in STUB_PATTERNS:
            if len(rx.findall(e.get("new") or "")) > len(rx.findall(e.get("old") or "")):
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
        {"type": "assistant", "message": {"usage": {"output_tokens": 50,
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
    assert t["tests"] == [{"command": "pytest -q tests/", "failed": True}]
    assert t["verified"] and t["skills"] == ["pantheon:hydra"]
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
    assert 45 <= context_pct(p) <= 55                       # 100k of 200k
    assert context_pct("/nonexistent") == -1
    assert is_code_file("a/b.py") and not is_code_file("a/b.md") and not is_code_file("x")
    assert not FAIL_RE.search("0 failed, 12 passed")
    print("selftest ok — turn scan, stub diff, test verdicts, context%")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
