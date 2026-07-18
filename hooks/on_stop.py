#!/usr/bin/env python3
"""pantheon stop hook — learning capture, auto-receipts, and the verification gate.

Runs when the agent tries to finish a turn:
  1. CAPTURE — append the user's last message to the learning inbox (bounded);
     only a STRONG correction signal also stores a lesson — the inbox is the
     wide net, the store is curated fuel for recall.
  2. RECEIPTS — log which pantheon disciplines actually ran this turn, with
     the tokens they cost. The dashboard renders these.
  3. GATE — the enforcement feature. If this turn changed code and tests are
     failing, stubs (TODO/FIXME/.skip/.only) were introduced, or a non-trivial
     change shipped with no verification at all, the stop is BLOCKED and the
     agent is told exactly what to fix. Warn-only in economy, off in quiet.
     Hard evidence (failing checks, stubs) blocks at most twice per turn; the
     softer no-verification nudge blocks once — then the gate always yields
     (no infinite loops), and it fails OPEN if its counter can't persist.

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

OUR_SKILLS = {"ariadne", "sibyl", "daedalus", "prometheus", "hydra", "argus", "themis",
              "charon", "lethe", "mnemosyne", "athena", "alexandria", "arachne",
              "clio", "asclepius", "hephaestus"}

# Phrases that suggest the user is correcting or redirecting — worth a closer
# look during consolidation. Deliberately broad; consolidation drops the noise.
CORRECTION = re.compile(
    r"\b(no|not|don'?t|stop|wrong|actually|instead|isn'?t|aren'?t|"
    r"i said|i told you|you (didn'?t|did not|forgot|missed|keep)|"
    r"why (did|are|is)|that'?s not|never|again|still (not|doesn'?t|broken))\b",
    re.IGNORECASE,
)

# The broad net above only flags the INBOX. Auto-STORING a lesson (fuel that
# recall re-injects into future prompts) demands a strong, unambiguous signal —
# a stray "no"/"not"/"again" in ordinary conversation must never become memory.
STRONG_CORRECTION = re.compile(
    r"\b(i (said|told you|asked (you )?for)|you keep\b|you'?re still\b|"
    r"stop (doing|using|adding|writing)|that'?s (still )?wrong|"
    r"(from now on|always|never) (do|use|add|write|run|put|make|call|check)|"
    r"don'?t ever\b|remember (this|that|to)\b|my preference is)",
    re.IGNORECASE,
)


def inbox_path(cwd: str) -> str:
    """Project-local inbox if in a project, else a user-global one."""
    if cwd and os.path.isdir(cwd):
        return os.path.join(cwd, ".pantheon", "learning-inbox.md")
    return os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "learning-inbox.md")


def _bound_inbox(path: str) -> None:
    """Keep the inbox from growing forever: past 256KB, keep the last 64KB."""
    try:
        if os.path.getsize(path) > 262144:
            data = open(path, "rb").read()[-65536:]
            nl = data.find(b"\n")
            open(path, "wb").write(data[nl + 1:] if nl >= 0 else data)
    except Exception:
        pass


def capture(cwd: str, text: str) -> None:
    """Inbox line always (the wide net, bounded); a stored lesson only on a
    STRONG correction signal (the store is curated fuel for recall)."""
    if not text:
        return
    snippet = " ".join(text.split())[:280]
    flagged = bool(CORRECTION.search(text))
    flag = " ⚠️ likely-correction" if flagged else ""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    path = inbox_path(cwd)
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    if d.endswith(".pantheon"):  # project-local: keep the noisy file out of git
        gi = os.path.join(d, ".gitignore")
        if not os.path.isfile(gi):
            try:
                open(gi, "w", encoding="utf-8").write("learning-inbox.md\n")
            except Exception:
                pass
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"- [{stamp}]{flag} {snippet}\n")
    _bound_inbox(path)
    if flagged and STRONG_CORRECTION.search(text) and _store and len(snippet) >= 24:
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


def resolve_route(turn: dict, session: str, conn=None) -> None:
    """Close the loop for adaptive routing, straight from the store: the newest
    unresolved route for THIS session gets the observed outcome; older ones were
    superseded before the agent ever acted on them — resolve those 'ignored' so
    demotion stats finally see them. (A single shared last-route.json used to
    clobber every route but the last, starving the demotion feature.)"""
    if not _store or not session:
        return
    own = conn is None
    if own:
        conn = _store.connect()
    try:
        rows = conn.execute(
            "SELECT id, skill FROM routes WHERE session=? AND outcome='fired' "
            "ORDER BY id DESC LIMIT 20", (session,)).fetchall()
        if not rows:
            return
        invoked = {s.split(":")[-1] for s in turn.get("skills", [])}
        _store.set_route_outcome(conn, rows[0]["id"],
                                 route_outcome(rows[0]["skill"], invoked))
        for r in rows[1:]:
            _store.set_route_outcome(conn, r["id"], "ignored")
    finally:
        if own:
            conn.close()


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
        added = sum(e.get("added", 0) for e in code_edits)
        removed = sum(e.get("removed", 0) for e in code_edits)
        churn = max(added, removed)  # a 40-line deletion is as unverified as a 40-line add
        if failing:
            problems.append("verification is failing (" + "; ".join(failing[:3]) + ")")
        elif churn >= 15 and not turn.get("verified"):
            problems.append(f"{len(code_edits)} code file(s) changed (~{churn} lines) "
                            "but no verification passed (tests/build/lint/selftest)")
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


def gate_record_block(session: str, turn_key: str, used: int) -> bool:
    """True when the counter persisted. False = the yield valve is broken, so the
    caller must NOT block (fail-open) — otherwise an unwritable state dir would
    wedge the session in an infinite block loop."""
    try:
        return bool(_paths.write_json_atomic(
            _gate_state_path(session),
            {"turn_key": turn_key, "blocks": used + 1, "ts": time.time()}))
    except Exception:
        return False


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
    # hard evidence (failing checks, stubs) earns two blocks; the softer
    # "no verification ran" heuristic gets one nudge, then yields — a repo with
    # no test harness must not lose two turns to a demand it can't satisfy
    hard = any(p.startswith(("verification is failing", "stubs introduced"))
               for p in problems)
    limit = MAX_BLOCKS_PER_TURN if hard else 1
    used = gate_blocks_used(session, turn_key)
    if used >= limit:
        return {"systemMessage": f"⚠ pantheon gate yielded after {used} block(s) — still open: {summary}"}
    if not gate_record_block(session, turn_key, used):
        return {"systemMessage": f"⚠ pantheon gate (fail-open, counter unwritable): {summary}"}
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
    if used + 1 >= limit:
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
    global _store, _GATE_DIR
    assert CORRECTION.search("no, that's wrong")
    assert CORRECTION.search("you forgot to save it")
    assert not CORRECTION.search("please add a dark theme toggle")
    # the capture ladder: broad flags the inbox, only STRONG stores a lesson
    assert not STRONG_CORRECTION.search("no thanks, do the other one instead")
    assert not STRONG_CORRECTION.search("why did the build fail again?")
    assert not STRONG_CORRECTION.search("not sure about this approach")
    assert STRONG_CORRECTION.search("I told you to use tabs, stop using spaces")
    assert STRONG_CORRECTION.search("always use python3 for the hooks")
    assert STRONG_CORRECTION.search("that's wrong, the timeout is 300")
    assert STRONG_CORRECTION.search("remember this: I hate one-letter variables")
    assert STRONG_CORRECTION.search("you keep reverting my rename")
    # inbox: project dir gets a .gitignore, file stays bounded, line-aligned
    import tempfile
    cwd = tempfile.mkdtemp(prefix="pantheon-cap-")
    capture(cwd, "no that's not what I meant at all")
    ip = inbox_path(cwd)
    assert os.path.isfile(ip) and "likely-correction" in open(ip, encoding="utf-8").read()
    gi = open(os.path.join(cwd, ".pantheon", ".gitignore"), encoding="utf-8").read()
    assert "learning-inbox" in gi
    with open(ip, "w", encoding="utf-8") as f:
        f.write(("- [x] " + "y" * 120 + "\n") * 3000)
    _bound_inbox(ip)
    assert os.path.getsize(ip) <= 65536
    assert open(ip, "rb").read()[:1] == b"-"
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
    # a large unverified DELETION is churn too — added≈0 must not hide it
    turn_del = {"edits": [{"file": "a.py", "added": 1, "removed": 40, "new": "x",
                           "old": "\n" * 39}], "tests": [], "verified": False}
    assert any("no verification" in p for p in gate_check(turn_del))
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
    # two routed prompts before one Stop: latest gets the real outcome, the
    # superseded one resolves 'ignored' — nothing stays stuck at 'fired'
    if _store:
        import tempfile as _tf
        rconn = _store.connect(os.path.join(_tf.mkdtemp(prefix="pantheon-rr-"), "r.db"))
        r1 = _store.log_route(rconn, "hydra", "hydra", session="sR")
        r2 = _store.log_route(rconn, "athena", "athena", session="sR")
        r3 = _store.log_route(rconn, "lethe", "lethe", session="sOTHER")
        resolve_route({"skills": ["pantheon:athena"]}, "sR", rconn)
        got = {r["id"]: r["outcome"] for r in rconn.execute("SELECT id,outcome FROM routes")}
        assert got[r2] == "accepted" and got[r1] == "ignored" and got[r3] == "fired"
        rconn.close()
    # gate block counters live in one file per session — concurrent sessions
    # have no shared writer, so no clobber and no lost increments
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
    # block-limit ladder (store detached so selftest never writes the real DB):
    # soft problem (no verification) blocks ONCE then yields; hard (failing
    # tests) blocks twice; an unwritable counter dir fails OPEN, never wedges
    keep_store, _store = _store, None
    _GATE_DIR = tempfile.mkdtemp(prefix="pantheon-gl-")
    soft = dict(turn2, last_user="soft-turn")
    o1 = run_gate(soft, {"gate": "block"}, "sSoft", "")
    assert o1.get("decision") == "block" and "Final gate pass" in o1["reason"]
    o2 = run_gate(soft, {"gate": "block"}, "sSoft", "")
    assert "yielded" in o2.get("systemMessage", "")
    hardt = dict(turn, last_user="hard-turn")
    h1 = run_gate(hardt, {"gate": "block"}, "sHard", "")
    assert h1.get("decision") == "block" and "Final gate pass" not in h1["reason"]
    h2 = run_gate(hardt, {"gate": "block"}, "sHard", "")
    assert h2.get("decision") == "block" and "Final gate pass" in h2["reason"]
    h3 = run_gate(hardt, {"gate": "block"}, "sHard", "")
    assert "yielded" in h3.get("systemMessage", "")
    plain = os.path.join(tempfile.mkdtemp(prefix="pantheon-gw-"), "plainfile")
    open(plain, "w").write("x")
    _GATE_DIR = os.path.join(plain, "sub")  # dir creation will fail
    fo = run_gate(dict(turn2, last_user="q9"), {"gate": "block"}, "sWedge", "")
    assert "fail-open" in fo.get("systemMessage", "")
    _store = keep_store
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
