#!/usr/bin/env python3
"""pantheon stop hook — learning capture, auto-receipts, and the verification gate.

Runs when the agent tries to finish a turn:
  1. CAPTURE — append the user's last message to the learning inbox; when it
     smells like a correction, also store it as a lesson (fuel for recall).
  2. RECEIPTS — log which pantheon disciplines actually ran this turn, with
     the tokens they cost. The dashboard renders these.
  3. GATE — the enforcement feature. If this turn changed code and tests are
     failing, stubs (TODO/FIXME/.skip/.only) were introduced, or a non-trivial
     change shipped with no verification at all, the stop is BLOCKED and the
     agent is told exactly what to fix. Warn-only in economy, off in quiet.
     Max two blocks per turn — the third stop always passes (no infinite loops).

Design constraints: fail-silent (exit 0 on any error), stdlib only.
Self-check: python3 on_stop.py --selftest
"""
import sys, os, json, re, time, datetime, hashlib

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "lib"))
try:
    import config as _config
    import store as _store
    import paths as _paths
    import transcript as _tr
except Exception:
    _config = _store = _paths = _tr = None

OUR_SKILLS = {"ariadne", "oracle", "daedalus", "prometheus", "hydra", "argus", "themis",
              "charon", "lethe", "mnemosyne", "athena", "alexandria", "arachne",
              "dashboard", "doctor", "forge"}

# Phrases that suggest the user is correcting or redirecting — worth a closer
# look during consolidation. Deliberately broad; consolidation drops the noise.
CORRECTION = re.compile(
    r"\b(no|not|don'?t|stop|wrong|actually|instead|isn'?t|aren'?t|"
    r"i said|i told you|you (didn'?t|did not|forgot|missed|keep)|"
    r"why (did|are|is)|that'?s not|never|again|still (not|doesn'?t|broken))\b",
    re.IGNORECASE,
)


def inbox_path(cwd: str) -> str:
    """Project-local inbox if in a project, else a user-global one."""
    if cwd and os.path.isdir(cwd):
        return os.path.join(cwd, ".pantheon", "learning-inbox.md")
    return os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "learning-inbox.md")


def capture(cwd: str, text: str) -> None:
    """Inbox line always; a structured lesson when it reads like a correction."""
    if not text:
        return
    snippet = " ".join(text.split())[:280]
    flagged = bool(CORRECTION.search(text))
    flag = " ⚠️ likely-correction" if flagged else ""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    path = inbox_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"- [{stamp}]{flag} {snippet}\n")
    if flagged and _store and len(snippet) >= 24:
        try:
            conn = _store.connect()
            _store.add_lesson(conn, snippet, tags="correction,auto",
                              keys=_paths.project_name(cwd), source="auto")
            conn.close()
        except Exception:
            pass


def route_outcome(routed: str, invoked: set) -> str:
    """Pure decision: what happened to the routed skill this turn?"""
    if routed in invoked:
        return "accepted"
    if invoked & OUR_SKILLS:
        return "overridden"
    return "ignored"


def resolve_route(turn: dict, session: str) -> None:
    """Close the loop for adaptive routing: record whether the last routed
    skill was actually used, replaced with another discipline, or ignored."""
    p = os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "last-route.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        return
    if d.get("resolved") or d.get("session") != session or d.get("rowid") is None:
        return
    invoked = {s.split(":")[-1] for s in turn.get("skills", [])}
    outcome = route_outcome(d.get("skill", ""), invoked)
    if _store:
        conn = _store.connect()
        try:
            _store.set_route_outcome(conn, d["rowid"], outcome)
        finally:
            conn.close()
    d["resolved"], d["outcome"] = True, outcome
    json.dump(d, open(p, "w", encoding="utf-8"))


def auto_receipts(turn: dict, cfg: dict, session: str, cwd: str) -> None:
    """One receipt per pantheon skill invoked this turn. Skips when the skill
    already filed a richer manual receipt (via the CLI) in the last while."""
    if not cfg.get("receipts", True) or not _store:
        return
    names = {s.split(":")[-1] for s in turn.get("skills", [])} & OUR_SKILLS
    if not names:
        return
    conn = _store.connect()
    try:
        for name in sorted(names):
            # any recent receipt for this skill+session suppresses the auto one —
            # the Stop hook re-runs after each gate block and must not re-file
            row = conn.execute(
                "SELECT 1 FROM receipts WHERE skill=? AND session=? AND ts>? LIMIT 1",
                (name, session, time.time() - 1800)).fetchone()
            if row:
                continue
            _store.add_receipt(conn, name, "invoked", session=session,
                               tokens=turn.get("out_tokens", 0),
                               project=_paths.project_name(cwd))
    finally:
        conn.close()


# ── the verification gate ────────────────────────────────────────────────────
MAX_BLOCKS_PER_TURN = 2


def gate_check(turn: dict) -> list:
    """Return the list of problems that justify refusing 'done'. Pure logic."""
    code_edits = [e for e in turn.get("edits", []) if _tr.is_code_file(e.get("file", ""))]
    problems = []
    if code_edits:
        failing = [t["command"] for t in turn.get("tests", []) if t.get("failed")]
        if failing:
            problems.append("tests are failing (" + "; ".join(failing[:3]) + ")")
        added = sum(e.get("added", 0) for e in code_edits)
        if added >= 15 and not turn.get("verified"):
            problems.append(f"{len(code_edits)} code file(s) changed (~{added} lines) "
                            "but no verification ran (no tests/build/lint/selftest)")
    stubs = _tr.introduced_stubs(turn.get("edits", []))
    if stubs:
        problems.append("stubs introduced: " + ", ".join(stubs[:5]))
    return problems


_GATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "gate")


def _gate_state_path(session: str) -> str:
    """One file per session: concurrent sessions never share a writer, so there
    is no clobber and no read-modify-write race on the block counters (same-
    session Stop hooks are sequential by construction)."""
    sid = hashlib.md5((session or "no-session").encode()).hexdigest()[:12]
    return os.path.join(_GATE_DIR, f"{sid}.json")


def gate_blocks_used(session: str, turn_key: str) -> int:
    """turn_key is a hash of the prompt text, so an identical prompt hours later
    would collide with an exhausted counter — records expire after 2h."""
    try:
        rec = json.load(open(_gate_state_path(session), encoding="utf-8"))
        if rec.get("turn_key") == turn_key and time.time() - rec.get("ts", 0) < 7200:
            return int(rec.get("blocks", 0))
    except Exception:
        pass
    return 0


def gate_record_block(session: str, turn_key: str, used: int) -> None:
    try:
        p = _gate_state_path(session)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump({"turn_key": turn_key, "blocks": used + 1, "ts": time.time()},
                  open(p, "w", encoding="utf-8"))
    except Exception:
        pass


def run_gate(turn: dict, cfg: dict, session: str, cwd: str) -> dict:
    """Returns the hook output dict ({} = allow silently)."""
    mode = cfg.get("gate", "block")
    if mode == "off" or not turn.get("edits") and not turn.get("tests"):
        return {}
    problems = gate_check(turn)
    if not problems:
        return {}
    summary = "; ".join(problems)
    if mode == "warn":
        return {"systemMessage": f"⚠ pantheon gate (warn-only): {summary}"}
    turn_key = hashlib.md5((turn.get("last_user", "") or "?")[:2000].encode()).hexdigest()[:12]
    used = gate_blocks_used(session, turn_key)
    if used >= MAX_BLOCKS_PER_TURN:
        return {"systemMessage": f"⚠ pantheon gate yielded after {used} blocks — still open: {summary}"}
    gate_record_block(session, turn_key, used)
    try:
        if _store:
            conn = _store.connect()
            _store.add_receipt(conn, "gate", f"blocked: {summary}", session=session,
                               project=_paths.project_name(cwd))
            _store.add_metric(conn, "gate_block", 1, summary[:120])
            conn.close()
    except Exception:
        pass
    reason = (f"pantheon verification gate — do not finish yet: {summary}. "
              "Before stopping again: make the failing tests pass, remove the introduced "
              "stubs (TODO/FIXME/.skip/.only/NotImplementedError), or run a real verification "
              "(tests / build / lint / selftest) on the code you changed and report the result. "
              "If the user explicitly told you to skip verification, say so in one line and stop.")
    if used + 1 >= MAX_BLOCKS_PER_TURN:
        reason += " (Final gate pass — the next stop will be allowed.)"
    return {"decision": "block", "reason": reason}


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd") or os.getcwd()
    session = payload.get("session_id", "")
    cfg = _config.load(cwd) if _config else {"gate": "off", "receipts": False}
    turn = {}
    if _tr:
        try:
            turn = _tr.scan_turn(payload.get("transcript_path", ""))
        except Exception:
            turn = {}
    try:
        capture(cwd, turn.get("last_user", ""))
    except Exception:
        pass
    try:
        auto_receipts(turn, cfg, session, cwd)
    except Exception:
        pass
    try:
        resolve_route(turn, session)
    except Exception:
        pass
    out = {}
    try:
        out = run_gate(turn, cfg, session, cwd)
    except Exception:
        out = {}
    if out:
        print(json.dumps(out))
    return 0


def selftest() -> int:
    assert CORRECTION.search("no, that's wrong")
    assert CORRECTION.search("you forgot to save it")
    assert not CORRECTION.search("please add a dark theme toggle")
    # gate: failing tests on a code change → block-worthy
    turn = {"last_user": "x", "edits": [{"file": "a.py", "added": 3, "new": "x=1", "old": ""}],
            "tests": [{"command": "pytest", "failed": True}], "verified": True}
    assert any("failing" in p for p in gate_check(turn))
    # gate: big unverified change → block-worthy; small one → fine
    turn2 = {"edits": [{"file": "a.py", "added": 40, "new": "\n" * 39, "old": ""}],
             "tests": [], "verified": False}
    assert any("no verification" in p for p in gate_check(turn2))
    turn3 = {"edits": [{"file": "a.py", "added": 3, "new": "x=1", "old": ""}],
             "tests": [], "verified": False}
    assert gate_check(turn3) == []
    # gate: stub introduced via an Edit is caught even when verified
    # (a Write with no old baseline is deliberately NOT flagged — see transcript.py)
    turn4 = {"edits": [{"file": "a.py", "added": 2, "new": "x = 1  # TODO later",
                        "old": "x = 1"}],
             "tests": [{"command": "pytest", "failed": False}], "verified": True}
    assert any("stubs" in p for p in gate_check(turn4))
    # docs-only turns never gate
    turn5 = {"edits": [{"file": "README.md", "added": 99, "new": "TODO: docs", "old": ""}],
             "tests": [], "verified": False}
    assert gate_check(turn5) == []
    # warn mode wording + off mode silence
    out = run_gate(dict(turn4, last_user="q"), {"gate": "warn"}, "s", "")
    assert "systemMessage" in out and "warn-only" in out["systemMessage"]
    assert run_gate(turn4, {"gate": "off"}, "s", "") == {}
    # adaptive-routing outcome decision
    assert route_outcome("hydra", {"hydra"}) == "accepted"
    assert route_outcome("hydra", {"lethe"}) == "overridden"
    assert route_outcome("hydra", set()) == "ignored"
    assert route_outcome("my-custom", {"my-custom"}) == "accepted"
    # gate block counters live in one file per session — concurrent sessions
    # have no shared writer, so no clobber and no lost increments
    global _GATE_DIR
    import tempfile
    _GATE_DIR = tempfile.mkdtemp(prefix="pantheon-gs-")
    gate_record_block("sessA", "t1", 0)
    gate_record_block("sessB", "t9", 0)
    gate_record_block("sessA", "t1", 1)
    assert gate_blocks_used("sessA", "t1") == 2
    assert gate_blocks_used("sessB", "t9") == 1
    assert gate_blocks_used("sessA", "t2") == 0   # new turn resets
    assert gate_blocks_used("sessZ", "t1") == 0   # unknown session starts clean
    assert _gate_state_path("a") != _gate_state_path("b")
    # identical prompt text hours later must not inherit the exhausted counter
    stale = json.load(open(_gate_state_path("sessA"), encoding="utf-8"))
    stale["ts"] = time.time() - 8000
    json.dump(stale, open(_gate_state_path("sessA"), "w", encoding="utf-8"))
    assert gate_blocks_used("sessA", "t1") == 0
    print("selftest ok — capture regex, gate rules (fail/unverified/stub/docs), "
          "modes, route outcomes")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)  # a hook must never break the session
