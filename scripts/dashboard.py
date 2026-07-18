#!/usr/bin/env python3
"""pantheon dashboard — what the plugin did, caught, spent, and learned.

Full-screen curses TUI on a real terminal (`pantheon dashboard`), plain text
with `--plain` (what the clio skill shows in-session). Reads only local
state: the SQLite store + the HUD's spend ledger. stdlib only, no network.

Self-check: python3 dashboard.py --selftest
"""
import sys, os, json, time, datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lib"))
import store, paths
import config as cfgmod

BARS = " ▁▂▃▄▅▆▇█"
HEAT_DAYS = 14


def spark(vals):
    hi = max(vals) if vals and max(vals) > 0 else 0
    if not hi:
        return " " * len(vals)
    return "".join(BARS[min(8, max(0, int(round(v / hi * 8))))] for v in vals)


def _day_index(ts, days):
    """0..days-1 slot for a timestamp (days-1 = today), or None if older."""
    age = int((time.time() - ts) // 86400)
    return (days - 1 - age) if 0 <= age < days else None


def spend_series(days=7):
    """(per-day list, today, last-hour) from the HUD ledger."""
    series = [0.0] * days
    hour = 0.0
    h1 = time.time() - 3600
    try:
        for ln in open(os.path.join(paths.state_dir(), "usage-events.jsonl"),
                       encoding="utf-8"):
            try:
                e = json.loads(ln)
                t = datetime.datetime.fromisoformat(e["t"]).timestamp()
            except Exception:
                continue
            i = _day_index(t, days)
            if i is not None:
                series[i] += e["d"]
            if t >= h1:
                hour += e["d"]
    except Exception:
        pass
    return series, series[-1], hour


def gather(cwd="", db_path=""):
    conn = store.connect(db_path) if db_path else store.connect()
    try:
        c = store.counts(conn)
        receipts = store.recent_receipts(conn, limit=12, days=HEAT_DAYS)
        heat = {}
        for r in conn.execute("SELECT ts, skill FROM receipts WHERE ts>?",
                              (time.time() - HEAT_DAYS * 86400,)):
            i = _day_index(r["ts"], HEAT_DAYS)
            if i is None:
                continue
            heat.setdefault(r["skill"], [0] * HEAT_DAYS)[i] += 1
        gate_blocks = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE kind='gate_block' AND ts>?",
            (time.time() - 7 * 86400,)).fetchone()[0]
        ok = conn.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        conn.close()
    try:
        with open(os.path.join(_ROOT, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as f:
            version = json.load(f).get("version", "?")
    except Exception:
        version = "?"
    route_age = ""
    try:
        p = os.path.join(paths.state_dir(), "last-route.json")
        d = json.load(open(p, encoding="utf-8"))
        mins = int((time.time() - os.path.getmtime(p)) // 60)
        route_age = f"{d.get('skill', '?')} {mins}m ago"
    except Exception:
        pass
    series, today, hour = spend_series()
    return {"version": version, "counts": c, "receipts": receipts, "heat": heat,
            "spend": {"series": series, "today": today, "hour": hour,
                      "week": sum(series)},
            "cfg": cfgmod.load(cwd), "db_ok": ok == "ok",
            "gate_blocks_7d": gate_blocks, "last_route": route_age}


def _age(ts):
    d = max(0, time.time() - ts)
    return f"{int(d // 60)}m" if d < 3600 else (f"{int(d // 3600)}h" if d < 86400
                                                else f"{int(d // 86400)}d")


def render(data):
    c, sp, cfg = data["counts"], data["spend"], data["cfg"]
    lines = [
        f"🏛  pantheon v{data['version']} — dashboard",
        f"store: {c['lessons']} lessons · {c['receipts']} receipts · "
        f"{c['routes']} routes   config: {cfg['preset']} "
        f"(routing {cfg['routing']} · gate {cfg['gate']} · recall {cfg['recall']})",
        "",
        f"spend  7d ${sp['week']:.2f} {spark(sp['series'])}   "
        f"today ${sp['today']:.2f} · last hour ${sp['hour']:.2f}",
        "",
        f"discipline heat — last {HEAT_DAYS} days",
    ]
    if data["heat"]:
        width = max(len(k) for k in data["heat"])
        for skill, days in sorted(data["heat"].items(),
                                  key=lambda kv: -sum(kv[1])):
            lines.append(f"  {skill:<{width}}  {spark(days)}  {sum(days)}")
    else:
        lines.append("  (no receipts yet — disciplines file them as they run)")
    lines += ["", "recent receipts"]
    if data["receipts"]:
        for r in data["receipts"]:
            tok = f" · {r['tokens']}tok" if r["tokens"] else ""
            lines.append(f"  {_age(r['ts']):>3} · {r['skill']:<10} {r['note'][:76]}{tok}")
    else:
        lines.append("  (none yet)")
    lines += ["",
              f"health: db {'✓' if data['db_ok'] else '✗ CORRUPT — run pantheon doctor'} · "
              f"gate blocks 7d: {data['gate_blocks_7d']}"
              + (f" · last route: {data['last_route']}" if data["last_route"] else "")]
    return lines


def run_curses():
    import curses

    def loop(scr):
        curses.curs_set(0)
        scr.timeout(2000)
        while True:
            try:
                data = gather(os.getcwd())
                lines = render(data) + ["", "q quit · refreshes every 2s"]
            except Exception as e:
                lines = ["pantheon dashboard — store unavailable", str(e)]
            scr.erase()
            h, w = scr.getmaxyx()
            for i, ln in enumerate(lines[: h - 1]):
                try:
                    scr.addstr(i, 0, ln[: w - 1])
                except Exception:
                    pass
            scr.refresh()
            ch = scr.getch()
            if ch in (ord("q"), ord("Q"), 27):
                break

    curses.wrapper(loop)


def main(argv):
    if "--plain" in argv or not sys.stdout.isatty():
        print("\n".join(render(gather(os.getcwd()))))
        return 0
    try:
        run_curses()
    except Exception:
        print("\n".join(render(gather(os.getcwd()))))  # curses unavailable → plain
    return 0


def selftest() -> int:
    import tempfile
    db = os.path.join(tempfile.mkdtemp(prefix="pantheon-dash-"), "t.db")
    conn = store.connect(db)
    store.add_lesson(conn, "always run the selftests before shipping a hook change")
    store.add_receipt(conn, "hydra", "root-caused the chrome leak", tokens=900)
    store.add_receipt(conn, "lethe", "deleted 340 lines of dead code")
    store.add_metric(conn, "gate_block", 1, "tests failed")
    conn.close()
    data = gather(db_path=db)
    out = "\n".join(render(data))
    assert "pantheon v" in out and "1 lessons" in out.replace("lessons", "lessons", 1)
    assert "hydra" in out and "chrome leak" in out and "lethe" in out
    assert data["gate_blocks_7d"] == 1 and data["db_ok"]
    assert spark([0, 0, 0]) == "   " and len(spark([1, 5, 9])) == 3
    assert spark([1, 5, 9])[-1] == "█"
    print("selftest ok — gather + render on a seeded store")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main(sys.argv[1:]))
