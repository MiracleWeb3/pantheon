#!/usr/bin/env python3
"""pantheon limits — subscription usage windows (5-hour block + weekly), from
the only ground truth available locally: real token usage in the Claude Code
transcripts under ~/.claude/projects/.

Claude subscription plans meter a rolling 5-hour session window and a weekly
cap. Neither the statusline payload nor any local file exposes the meters, so
we rebuild them the way ccusage-style tools do:

  * every transcript JSONL line carrying `usage` is aggregated into per-hour
    token buckets (input + output + cache-create + cache-read, deduped by
    message id — Claude Code writes one line per content block, repeating the
    same usage);
  * scanning is INCREMENTAL: a per-file byte offset means each statusline
    render reads only what was appended since the last one;
  * the 5h window is block-anchored like Claude's own reset: a block starts at
    the floor-hour of the first activity after the previous block elapsed;
  * limits aren't published, so percentages calibrate against the largest
    block / week ever observed (shown with ≈), unless the user pins exact
    numbers in config: {"usage": {"five_hour_tokens": N, "weekly_tokens": N}}.

stdlib only, fail-soft. Self-check: python3 limits.py --selftest
"""
import os, json, time, datetime

import paths

PROJECTS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects")
CREDENTIALS = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")
CACHE_NAME = "usage-windows.json"

BLOCK_HOURS = 5
WEEK_HOURS = 7 * 24
KEEP_HOURS = 8 * 24  # bucket retention


def _cache_path() -> str:
    return os.path.join(paths.state_dir(), CACHE_NAME)


def _load_cache() -> dict:
    try:
        c = json.load(open(_cache_path(), encoding="utf-8"))
        if isinstance(c, dict):
            c.setdefault("files", {})
            c.setdefault("buckets", {})
            return c
    except Exception:
        pass
    return {"files": {}, "buckets": {}, "max_block": 0, "max_week": 0}


def _save_cache(c: dict) -> None:
    try:
        paths.write_json_atomic(_cache_path(), c)
    except Exception:
        pass


def _hour_key(ts_iso: str) -> str:
    return ts_iso[:13]  # YYYY-MM-DDTHH — sorts chronologically


def _hour_ts(key: str) -> float:
    try:
        return datetime.datetime.fromisoformat(key + ":00:00+00:00").timestamp()
    except Exception:
        return 0.0


def _ingest_line(line: str, buckets: dict, seen_ids: set) -> None:
    if '"usage"' not in line:
        return
    try:
        obj = json.loads(line)
    except Exception:
        return
    msg = obj.get("message") or {}
    u = msg.get("usage")
    if not isinstance(u, dict):
        return
    mid = msg.get("id") or obj.get("requestId")
    if mid:
        if mid in seen_ids:
            return
        seen_ids.add(mid)
    ts = obj.get("timestamp") or ""
    if not isinstance(ts, str) or len(ts) < 13:
        return
    tokens = ((u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
              + (u.get("cache_creation_input_tokens") or 0)
              + (u.get("cache_read_input_tokens") or 0))
    if tokens > 0:
        k = _hour_key(ts)
        buckets[k] = buckets.get(k, 0) + tokens


def _transcript_files(c: dict, now: float) -> list:
    """All transcript paths, with the os.walk memoized for 120s — the walk
    scales with total project count and ran on every statusline render.
    ponytail: a brand-new session's file shows up ≤2min late on the fallback
    meter; known files are still stat'ed fresh every render."""
    if now - float(c.get("walk_at") or 0) < 120 and isinstance(c.get("walk_files"), list):
        return c["walk_files"]
    files = []
    try:
        for base, _dirs, fns in os.walk(PROJECTS_DIR):
            for fn in fns:
                if fn.endswith(".jsonl"):
                    files.append(os.path.join(base, fn))
    except Exception:
        pass
    c["walk_at"], c["walk_files"] = now, files
    return files


def scan(now: float = 0.0) -> dict:
    """Update the bucket cache from transcripts (incremental) and return it."""
    now = now or time.time()
    c = _load_cache()
    fresh_after = now - KEEP_HOURS * 3600
    try:
        for p in _transcript_files(c, now):
                try:
                    st = os.stat(p)
                except Exception:
                    continue
                if st.st_mtime < fresh_after:
                    c["files"].pop(p, None)
                    continue
                rec = c["files"].get(p) or {"offset": 0}
                if st.st_size == rec.get("offset"):
                    continue
                start = rec.get("offset", 0)
                if start > st.st_size:
                    start = 0  # truncated/rotated — rescan
                cap_seek = False
                if st.st_size - start > 30_000_000:
                    start = st.st_size - 30_000_000  # cap pathological catch-ups
                    cap_seek = True
                seen = set()
                try:
                    with open(p, "rb") as f:
                        f.seek(start)
                        data = f.read()
                    # drop a partial first line ONLY after an artificial seek —
                    # a saved offset sits on a line boundary, and dropping there
                    # would eat the first appended entry
                    if cap_seek and b"\n" in data:
                        data = data.split(b"\n", 1)[1]
                    for line in data.decode("utf-8", "replace").splitlines():
                        _ingest_line(line, c["buckets"], seen)
                    c["files"][p] = {"offset": st.st_size}
                except Exception:
                    continue
    except Exception:
        pass
    # prune old buckets + forgotten files
    cutoff = _hour_key(datetime.datetime.fromtimestamp(
        fresh_after, datetime.timezone.utc).isoformat())
    c["buckets"] = {k: v for k, v in c["buckets"].items() if k >= cutoff}
    return c


def current_block(buckets: dict, now: float):
    """(block_start_ts, tokens_in_block, reset_ts) with Claude-style anchoring:
    a block opens at the floor-hour of the first activity after the previous
    block elapsed. Returns (None, 0, None) when the last block has elapsed."""
    start = None
    for k in sorted(buckets):
        ts = _hour_ts(k)
        if not ts:
            continue
        if start is None or ts >= start + BLOCK_HOURS * 3600:
            start = ts
    if start is None or now >= start + BLOCK_HOURS * 3600:
        return None, 0, None
    end = start + BLOCK_HOURS * 3600
    tokens = sum(v for k, v in buckets.items()
                 if start <= _hour_ts(k) < end)
    return start, tokens, end


def week_tokens(buckets: dict, now: float) -> int:
    cutoff = now - WEEK_HOURS * 3600
    return sum(v for k, v in buckets.items() if _hour_ts(k) >= cutoff)


def detect_mode(cfg_usage: dict) -> str:
    mode = (cfg_usage or {}).get("mode", "auto")
    if mode in ("subscription", "api"):
        return mode
    try:
        if "claudeAiOauth" in open(CREDENTIALS, encoding="utf-8").read(2000):
            return "subscription"
    except Exception:
        pass
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "api"
    return "subscription"  # Claude Code's common case


def windows(cfg_usage: dict = None, now: float = 0.0) -> dict:
    """The HUD's one call. Returns:
       {mode, block_tokens, block_pct|None, block_reset_min|None,
        week_tokens, week_pct|None, approx}  — pct None when no denominator."""
    now = now or time.time()
    cfg_usage = cfg_usage or {}
    mode = detect_mode(cfg_usage)
    c = scan(now)
    _, btok, bend = current_block(c["buckets"], now)
    wtok = week_tokens(c["buckets"], now)
    c["max_block"] = max(int(c.get("max_block") or 0), btok)
    c["max_week"] = max(int(c.get("max_week") or 0), wtok)
    _save_cache(c)

    def pct(cur, configured, observed):
        if isinstance(configured, (int, float)) and configured > 0:
            return min(999, int(round(cur / configured * 100))), False
        if observed > 0 and cur > 0:
            return min(999, int(round(cur / observed * 100))), True
        return None, False

    bpct, bapprox = pct(btok, cfg_usage.get("five_hour_tokens"), int(c.get("max_block") or 0))
    wpct, wapprox = pct(wtok, cfg_usage.get("weekly_tokens"), int(c.get("max_week") or 0))
    return {"mode": mode, "block_tokens": btok, "block_pct": bpct,
            "block_reset_min": int((bend - now) // 60) if bend else None,
            "week_tokens": wtok, "week_pct": wpct,
            "approx": bapprox or wapprox}


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n // 1_000}k"
    return str(n)


def selftest() -> int:
    import tempfile
    global PROJECTS_DIR
    old_projects, old_state = PROJECTS_DIR, paths.state_dir
    root = tempfile.mkdtemp(prefix="pantheon-lim-")
    PROJECTS_DIR = os.path.join(root, "projects")
    paths.state_dir = lambda: root  # cache lands in the temp root
    d = os.path.join(PROJECTS_DIR, "proj-a")
    os.makedirs(d)
    now = time.time()

    def iso(h_ago):
        return datetime.datetime.fromtimestamp(
            now - h_ago * 3600, datetime.timezone.utc).isoformat()

    def entry(h_ago, mid, out=100, cin=50, cread=1000):
        return json.dumps({"timestamp": iso(h_ago), "type": "assistant",
                           "message": {"id": mid, "usage": {
                               "input_tokens": cin, "output_tokens": out,
                               "cache_creation_input_tokens": 10,
                               "cache_read_input_tokens": cread}}})

    p = os.path.join(d, "s1.jsonl")
    with open(p, "w") as f:
        f.write(entry(10, "old1") + "\n")          # old block (elapsed)
        f.write(entry(1, "m1") + "\n")
        f.write(entry(1, "m1") + "\n")             # duplicate line, same id
        f.write(entry(0.5, "m2") + "\n")
    w = windows({}, now=now)
    per = 100 + 50 + 10 + 1000                      # 1160 per unique message
    assert w["block_tokens"] == 2 * per, w          # m1 counted once + m2
    assert w["week_tokens"] == 3 * per, w           # old1 in week, in no block
    assert w["block_reset_min"] and 0 < w["block_reset_min"] <= 300
    # incremental: appending one entry adds exactly one message's tokens
    with open(p, "a") as f:
        f.write(entry(0.2, "m3") + "\n")
    w2 = windows({}, now=now)
    assert w2["block_tokens"] == 3 * per, w2
    # configured limits give exact percentages; calibration marks approx
    w3 = windows({"five_hour_tokens": 6 * per, "weekly_tokens": 8 * per}, now=now)
    assert w3["block_pct"] == 50 and w3["week_pct"] == 50 and not w3["approx"]
    w4 = windows({}, now=now)
    assert w4["block_pct"] == 100 and w4["approx"]  # calibrated on observed max
    # elapsed block → 0 current
    _, btok, _ = current_block({_hour_key(iso(10)): 500}, now)
    assert btok == 0
    assert fmt_tokens(8_400_000) == "8.4M" and fmt_tokens(950_000) == "950k"
    assert detect_mode({"mode": "api"}) == "api"
    PROJECTS_DIR = old_projects
    paths.state_dir = old_state
    print("selftest ok — buckets, dedupe, block anchor, incremental, pct, calibration")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else
                     print(json.dumps(windows({}), indent=2)) or 0)
