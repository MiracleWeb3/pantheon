#!/usr/bin/env python3
"""pantheon HUD — a richer Claude Code statusline than the defaults.

Segments (each shown only when it has real data):
  🏛 discipline · model · effort · ⧗session-time · ▓context% · +adds/-rems ·
  $session · ⧖1h-spend · wk-spend · ⎇branch · 📥learning-inbox

Everything is sourced from the real statusline payload
(model, cost.total_cost_usd, cost.total_duration_ms, cost.total_lines_added/removed,
exceeds_200k_tokens, transcript_path, session_id) plus two things pantheon derives
itself and Claude Code does NOT give you:
  • rolling hourly / weekly SPEND — a per-session cost-delta ledger.
  • live CONTEXT fill % — estimated from the transcript size.
  • current EFFORT — read from the transcript (/effort output).

Setup — one line in ~/.claude/settings.json:
  "statusLine": { "type": "command",
    "command": "python3 ~/.claude/plugins/marketplaces/pantheon/scripts/hud.py" }
Chain an existing statusline:  ... hud.py --chain 'your-command'

Fail-silent: a broken statusline is worse than none. Self-check: python3 hud.py --selftest
"""
import sys, os, json, datetime

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
CYAN, MAGENTA, YELLOW, GREEN, RED = ("\033[36m", "\033[35m", "\033[33m",
                                     "\033[32m", "\033[31m")
CTX_WINDOW = 200_000          # tokens; the mainline context budget
BYTES_PER_TOKEN = 3.7         # rough transcript-bytes → tokens
PANDIR = os.path.join(os.path.expanduser("~"), ".claude", "pantheon")


# ── real-data helpers ────────────────────────────────────────────────────────
def git_branch(cwd):
    d = cwd
    for _ in range(12):
        head, gf = os.path.join(d, ".git", "HEAD"), os.path.join(d, ".git")
        if os.path.isfile(gf) and not os.path.isdir(gf):
            line = open(gf, encoding="utf-8").read().strip()
            if line.startswith("gitdir:"):
                head = os.path.join(line.split(":", 1)[1].strip(), "HEAD")
        if os.path.isfile(head):
            ref = open(head, encoding="utf-8").read().strip()
            return ref.rsplit("/", 1)[-1] if ref.startswith("ref:") else ref[:8]
        p = os.path.dirname(d)
        if p == d:
            break
        d = p
    return ""


def last_route():
    try:
        d = json.load(open(os.path.join(PANDIR, "last-route.json"), encoding="utf-8"))
        at = datetime.datetime.fromisoformat(d["at"])
        if (datetime.datetime.now() - at).total_seconds() < 4 * 3600:
            return d.get("skill", "")
    except Exception:
        pass
    return ""


def inbox_count(cwd):
    n = 0
    for p in (os.path.join(cwd, ".pantheon", "learning-inbox.md"),
              os.path.join(PANDIR, "learning-inbox.md")):
        try:
            n += sum(1 for ln in open(p, encoding="utf-8") if ln.lstrip().startswith("-"))
        except Exception:
            pass
    return n


def context_pct(transcript_path):
    """% of the context window filled, from the LAST turn's real token usage.
    The transcript is append-only (grows forever), so its size is meaningless;
    the live context size is the input side of the most recent usage record."""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            if size > 512_000:
                f.seek(size - 512_000)
            lines = f.read().decode("utf-8", "replace").splitlines()
        for ln in reversed(lines):
            ln = ln.strip()
            if '"usage"' not in ln:
                continue
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            u = (obj.get("message") or {}).get("usage") or obj.get("usage")
            if not isinstance(u, dict):
                continue
            tokens = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                      + u.get("cache_creation_input_tokens", 0))
            if tokens > 0:
                return min(100, int(tokens / CTX_WINDOW * 100))
        return -1
    except Exception:
        return -1


def effort(transcript_path, session_id):
    """Most recent /effort level. /effort is usually set once at the start, so
    a tail read misses it in long sessions. We scan incrementally: a per-session
    byte offset means the whole file is scanned once, then only appended bytes."""
    import re
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    key = session_id or transcript_path
    cache_p = os.path.join(PANDIR, "effort.json")
    cache = {}
    try:
        cache = json.load(open(cache_p, encoding="utf-8"))
    except Exception:
        pass
    rec = cache.get(key, {"effort": "", "offset": 0})
    try:
        size = os.path.getsize(transcript_path)
        start = rec["offset"] if rec["offset"] <= size else 0
        with open(transcript_path, "rb") as f:
            if size - start > 25_000_000:      # pathological: cap the catch-up read
                start = size - 4_000_000
            f.seek(start)
            chunk = f.read().decode("utf-8", "replace")
        m = re.findall(r"effort level to (\w+)", chunk, re.IGNORECASE)
        if m:
            rec["effort"] = m[-1].lower()
        rec["offset"] = size
        cache[key] = rec
        os.makedirs(PANDIR, exist_ok=True)
        json.dump(cache, open(cache_p, "w", encoding="utf-8"))
    except Exception:
        pass
    return rec.get("effort", "")


def usage(session_id, total_cost):
    """Roll a per-session cost-delta ledger → (spend_1h, spend_24h, spend_7d).
    Claude Code exposes only cumulative session cost, so we diff it ourselves."""
    if not session_id or not isinstance(total_cost, (int, float)):
        return None, None, None
    try:
        os.makedirs(PANDIR, exist_ok=True)
        state_p = os.path.join(PANDIR, "usage-state.json")
        ev_p = os.path.join(PANDIR, "usage-events.jsonl")
        state = {}
        try:
            state = json.load(open(state_p, encoding="utf-8"))
        except Exception:
            pass
        prev = state.get(session_id, 0.0)
        delta = total_cost - prev if total_cost >= prev else total_cost
        now = datetime.datetime.now()
        if delta > 1e-9:
            with open(ev_p, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": now.isoformat(), "d": round(delta, 6)}) + "\n")
            state[session_id] = total_cost
            json.dump(state, open(state_p, "w", encoding="utf-8"))
        h1 = now - datetime.timedelta(hours=1)
        d1 = now - datetime.timedelta(days=1)
        d7 = now - datetime.timedelta(days=7)
        s1 = s24 = s7 = 0.0
        keep = []
        try:
            for ln in open(ev_p, encoding="utf-8"):
                try:
                    e = json.loads(ln)
                    t = datetime.datetime.fromisoformat(e["t"])
                except Exception:
                    continue
                if t >= d7:
                    keep.append(ln)
                    s7 += e["d"]
                    if t >= d1:
                        s24 += e["d"]
                    if t >= h1:
                        s1 += e["d"]
            if len(keep) > 5000:  # prune the log opportunistically
                open(ev_p, "w", encoding="utf-8").writelines(keep)
        except Exception:
            pass
        return s1, s24, s7
    except Exception:
        return None, None, None


def budget_flag(session_cost, s24, s7):
    """'' | 'near' | 'over' against the config budget caps. Uses a file-scoped
    import so a broken lib/ can never take the statusline down with it."""
    try:
        import importlib.util
        lib = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "lib", "config.py")
        spec = importlib.util.spec_from_file_location("pantheon_cfg", lib)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        b = mod.load(os.getcwd()).get("budget") or {}
    except Exception:
        return ""
    out = ""
    for scope, spend in (("session", session_cost), ("daily", s24), ("weekly", s7)):
        cap = b.get(scope)
        if isinstance(cap, (int, float)) and cap > 0:
            if spend >= cap:
                return "over"
            if spend >= 0.8 * cap:
                out = "near"
    return out


def fmt_dur(ms):
    try:
        s = int(ms) // 1000
    except Exception:
        return ""
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


# ── line builder ─────────────────────────────────────────────────────────────
def build_line(p):
    ws = p.get("workspace") or {}
    cwd = ws.get("current_dir") or p.get("cwd") or os.getcwd()
    cost = p.get("cost") or {}
    seg = [f"{MAGENTA}🏛{RESET}"]

    skill = last_route()
    if skill:
        seg.append(f"{BOLD}{MAGENTA}{skill}{RESET}")
    model = (p.get("model") or {}).get("display_name")
    if model:
        seg.append(f"{CYAN}{model}{RESET}")
    ef = effort(p.get("transcript_path", ""), p.get("session_id"))
    if ef:
        col = RED if ef in ("max", "xhigh") else YELLOW
        seg.append(f"{col}✳{ef}{RESET}")
    dur = fmt_dur(cost.get("total_duration_ms"))
    if dur:
        seg.append(f"{DIM}⧗{dur}{RESET}")

    pct = context_pct(p.get("transcript_path", ""))
    if p.get("exceeds_200k_tokens"):
        seg.append(f"{RED}▓ctx>200k{RESET}")
    elif pct >= 0:
        col = RED if pct >= 85 else YELLOW if pct >= 60 else GREEN
        seg.append(f"{col}▓{pct}%{RESET}")

    add, rem = cost.get("total_lines_added"), cost.get("total_lines_removed")
    if add or rem:
        seg.append(f"{GREEN}+{add or 0}{RESET}/{RED}-{rem or 0}{RESET}")

    tc = cost.get("total_cost_usd")
    if isinstance(tc, (int, float)) and tc > 0:
        seg.append(f"{DIM}${tc:.2f}{RESET}")
    s1, s24, s7 = usage(p.get("session_id"), tc)
    if s1 is not None and (s1 > 0 or s7 > 0):
        seg.append(f"{DIM}⧖1h{RESET} ${s1:.2f}")
        seg.append(f"{DIM}wk{RESET} ${s7:.2f}")
    flag = budget_flag(tc if isinstance(tc, (int, float)) else 0.0,
                       s24 or 0.0, s7 or 0.0)
    if flag == "over":
        seg.append(f"{RED}⚠budget{RESET}")
    elif flag == "near":
        seg.append(f"{YELLOW}budget≈{RESET}")

    br = git_branch(cwd)
    if br:
        seg.append(f"{DIM}⎇ {br}{RESET}")
    ib = inbox_count(cwd)
    if ib:
        seg.append(f"{YELLOW}📥{ib}{RESET}")
    return f" {DIM}·{RESET} ".join(seg)


def chained_line(raw, cmd):
    import subprocess
    try:
        r = subprocess.run(cmd, shell=True, input=raw.encode(),
                           capture_output=True, timeout=3)
        out = r.stdout.decode(errors="replace").strip().splitlines()
        return out[0] if out else ""
    except Exception:
        return ""


def main():
    raw = sys.stdin.read()
    p = json.loads(raw) if raw.strip() else {}
    mine = build_line(p)
    if "--chain" in sys.argv:
        i = sys.argv.index("--chain")
        cmd = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        other = chained_line(raw, cmd) if cmd else ""
        if other:
            print(f"{other} {DIM}·{RESET} {mine}")
            return 0
    print(mine)
    return 0


def selftest():
    # All ledger/cache writes go to a temp dir — the doctor runs this selftest
    # routinely, and it must never touch the user's real spend history.
    global PANDIR
    _old_pandir = PANDIR
    import tempfile
    PANDIR = tempfile.mkdtemp(prefix="pantheon-hud-")
    p = {"model": {"display_name": "Fable 5"},
         "workspace": {"current_dir": os.getcwd()},
         "session_id": "selftest-sess",
         "cost": {"total_cost_usd": 2.5, "total_duration_ms": 3_725_000,
                  "total_lines_added": 40, "total_lines_removed": 7},
         "exceeds_200k_tokens": False}
    line = build_line(p)
    assert "Fable 5" in line and "🏛" in line and "$2.50" in line
    assert "1h02m" in line, line          # 3,725s → 1h02m session time
    assert "+40" in line and "-7" in line
    assert fmt_dur(45_000) == "45s" and fmt_dur(90_000) == "1m"
    assert context_pct("/nonexistent") == -1
    assert git_branch("/nonexistent/path") == ""
    s1, s24, s7 = usage("selftest-sess", 2.5)  # first call: full 2.5 is the delta
    assert s1 is not None and s7 >= 2.5 and s24 >= 2.5, (s1, s24, s7)
    s1b, _, _ = usage("selftest-sess", 2.5)    # no change → no new delta
    assert budget_flag(0.0, 0.0, 0.0) == ""    # zero spend never flags
    assert chained_line("{}", "echo X") == "X" and chained_line("{}", "exit 1") == ""
    PANDIR = _old_pandir
    print("selftest ok —", line)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        print("🏛")
        raise SystemExit(0)
