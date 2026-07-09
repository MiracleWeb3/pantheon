#!/usr/bin/env python3
"""pantheon CLI — receipts, lessons, recall, stats, dashboard.

Reached via the shim `~/.claude/pantheon/bin/pantheon` (rewritten every
SessionStart to point at the installed plugin), or directly:
    python3 <plugin>/scripts/cli.py <command> ...

Commands:
    receipt add --skill S --note "..."     file a receipt for a discipline
    receipt list [--days 7]
    lesson add "text" [--tags a,b] [--keys proj] [--weight 1.3]
    lesson list [--limit 20] / lesson search "query"
    lesson import-inbox                    pull ⚠️-flagged inbox lines into the store
    recall "some prompt"                   debug what auto-recall would surface
    stats                                  counts, top disciplines, spend
    dashboard [--plain]                    the TUI (scripts/dashboard.py)
    version

stdlib only. Self-check: python3 cli.py --selftest
"""
import sys, os, json, time, argparse, datetime, subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lib"))
import store, paths
import config as cfgmod


def _session():
    return os.environ.get("CLAUDE_SESSION_ID", "")


def _age(ts):
    d = max(0, time.time() - ts)
    if d < 3600:
        return f"{int(d // 60)}m"
    if d < 86400:
        return f"{int(d // 3600)}h"
    return f"{int(d // 86400)}d"


def cmd_receipt(a):
    conn = store.connect()
    if a.action == "add":
        if not a.skill or not a.note:
            print("need --skill and --note")
            return 2
        rid = store.add_receipt(conn, a.skill, a.note, session=_session(),
                                tokens=a.tokens, project=paths.project_name(os.getcwd()))
        print(f"receipt #{rid} · {a.skill} — {a.note}")
    else:
        rows = store.recent_receipts(conn, limit=a.limit, days=a.days)
        if not rows:
            print("no receipts yet")
        for r in rows:
            tok = f" · {r['tokens']}tok" if r["tokens"] else ""
            proj = f" · {r['project']}" if r["project"] else ""
            print(f"{_age(r['ts']):>4} · {r['skill']:<10} {r['note']}{tok}{proj}")
    return 0


def cmd_lesson(a):
    conn = store.connect()
    if a.action == "add":
        lid = store.add_lesson(conn, a.text, tags=a.tags, weight=a.weight,
                               keys=a.keys or paths.project_name(os.getcwd()),
                               source="manual")
        print(f"lesson #{lid} saved" if lid else "skipped (duplicate or too short)")
        return 0
    if a.action == "import-inbox":
        n = 0
        for p in (os.path.join(os.getcwd(), ".pantheon", "learning-inbox.md"),
                  os.path.join(paths.state_dir(), "learning-inbox.md")):
            try:
                for ln in open(p, encoding="utf-8"):
                    if "likely-correction" in ln and ln.lstrip().startswith("-"):
                        text = ln.split("likely-correction", 1)[1].strip()
                        if store.add_lesson(conn, text, tags="correction,inbox",
                                            keys=paths.project_name(os.getcwd()),
                                            source="auto"):
                            n += 1
            except Exception:
                continue
        print(f"imported {n} flagged inbox line(s) as lessons "
              "(inbox files untouched — consolidate/delete them yourself)")
        return 0
    q = "SELECT * FROM lessons ORDER BY ts DESC LIMIT ?"
    args = [a.limit]
    if a.action == "search" and a.text:
        q = ("SELECT * FROM lessons WHERE text LIKE ? OR tags LIKE ? "
             "ORDER BY ts DESC LIMIT ?")
        like = f"%{a.text}%"
        args = [like, like, a.limit]
    rows = list(conn.execute(q, args))
    if not rows:
        print("no lessons yet — `pantheon lesson add \"...\"` or let capture feed them")
    for r in rows:
        uses = f" ·{r['uses']}×" if r["uses"] else ""
        print(f"#{r['id']:<4}{_age(r['ts']):>4} [{r['source']}{uses}] {r['text'][:110]}")
    return 0


def cmd_recall(a):
    conn = store.connect()
    hits = store.recall(conn, a.text, keys=paths.project_name(os.getcwd()), limit=3)
    if not hits:
        print("nothing clears the relevance bar for that prompt")
    for h in hits:
        print(f"• ({_age(h['ts'])}, {h['source']}) {h['text'][:160]}")
    return 0


def _spend():
    """(today, last-7d) USD from the HUD's ledger; (0, 0) when absent."""
    day = time.time() - 86400
    week = time.time() - 7 * 86400
    s1 = s7 = 0.0
    try:
        for ln in open(os.path.join(paths.state_dir(), "usage-events.jsonl"),
                       encoding="utf-8"):
            try:
                e = json.loads(ln)
                t = datetime.datetime.fromisoformat(e["t"]).timestamp()
            except Exception:
                continue
            if t >= week:
                s7 += e["d"]
                if t >= day:
                    s1 += e["d"]
    except Exception:
        pass
    return s1, s7


def cmd_stats(a):
    conn = store.connect()
    c = store.counts(conn)
    print(f"store: {c['lessons']} lessons · {c['receipts']} receipts · "
          f"{c['routes']} routes · {c['metrics']} metrics")
    rows = list(conn.execute(
        "SELECT skill, COUNT(*) n FROM receipts WHERE ts>? GROUP BY skill "
        "ORDER BY n DESC LIMIT 6", (time.time() - 7 * 86400,)))
    if rows:
        print("7d disciplines: " + " · ".join(f"{r['skill']}×{r['n']}" for r in rows))
    s1, s7 = _spend()
    if s7:
        print(f"spend: ${s1:.2f} today · ${s7:.2f} last 7d")
    cfg = cfgmod.load(os.getcwd())
    print(f"config: preset={cfg['preset']} routing={cfg['routing']} gate={cfg['gate']} "
          f"recall={cfg['recall']} receipts={cfg['receipts']}")
    return 0


def cmd_dashboard(a):
    args = [sys.executable, os.path.join(_HERE, "dashboard.py")]
    if a.plain:
        args.append("--plain")
    return subprocess.call(args)


def cmd_doctor(a):
    args = [sys.executable, os.path.join(_HERE, "doctor.py")]
    if a.fix:
        args.append("--fix")
    return subprocess.call(args)


def cmd_version(a):
    try:
        with open(os.path.join(_ROOT, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as f:
            print("pantheon v" + json.load(f).get("version", "?"))
    except Exception:
        print("pantheon (version unknown)")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="pantheon", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("receipt", help="file / list discipline receipts")
    r.add_argument("action", choices=["add", "list"])
    r.add_argument("--skill", default="")
    r.add_argument("--note", default="")
    r.add_argument("--tokens", type=int, default=0)
    r.add_argument("--days", type=float, default=7)
    r.add_argument("--limit", type=int, default=30)
    r.set_defaults(fn=cmd_receipt)

    l = sub.add_parser("lesson", help="add / list / search / import-inbox")
    l.add_argument("action", choices=["add", "list", "search", "import-inbox"])
    l.add_argument("text", nargs="?", default="")
    l.add_argument("--tags", default="")
    l.add_argument("--keys", default="")
    l.add_argument("--weight", type=float, default=1.3)
    l.add_argument("--limit", type=int, default=20)
    l.set_defaults(fn=cmd_lesson)

    rc = sub.add_parser("recall", help="debug: what auto-recall would surface")
    rc.add_argument("text")
    rc.set_defaults(fn=cmd_recall)

    st = sub.add_parser("stats", help="counts, top disciplines, spend")
    st.set_defaults(fn=cmd_stats)

    d = sub.add_parser("dashboard", help="live TUI (or --plain)")
    d.add_argument("--plain", action="store_true")
    d.set_defaults(fn=cmd_dashboard)

    dr = sub.add_parser("doctor", help="diagnose + fix the install")
    dr.add_argument("--fix", action="store_true")
    dr.set_defaults(fn=cmd_doctor)

    v = sub.add_parser("version")
    v.set_defaults(fn=cmd_version)
    return ap


def main(argv):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


def selftest() -> int:
    ap = build_parser()
    a = ap.parse_args(["receipt", "add", "--skill", "hydra", "--note", "x"])
    assert a.fn is cmd_receipt and a.skill == "hydra"
    a = ap.parse_args(["lesson", "add", "some text", "--tags", "t"])
    assert a.fn is cmd_lesson and a.text == "some text"
    a = ap.parse_args(["dashboard", "--plain"])
    assert a.fn is cmd_dashboard and a.plain
    a = ap.parse_args(["doctor", "--fix"])
    assert a.fn is cmd_doctor and a.fix
    assert _age(time.time() - 30) == "0m" and _age(time.time() - 90000) == "1d"
    s1, s7 = _spend()
    assert s1 >= 0 and s7 >= s1
    print("selftest ok — parser wiring, age fmt, spend reader")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main(sys.argv[1:]))
