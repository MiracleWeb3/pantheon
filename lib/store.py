#!/usr/bin/env python3
"""pantheon store — one SQLite substrate under every feature.

~/.claude/pantheon/pantheon.db (WAL, stdlib sqlite3, created on demand,
schema versioned in `meta`). Five tables:

  lessons   captured memory: text, tags, project keys, keyword index, weight
  receipts  per-discipline action log: skill, note, tokens, timestamp
  routes    router fires and their outcome (accepted/overridden/ignored)
  metrics   loose rollups (gate blocks, doctor runs, ...)
  meta      schema version, pack-import markers, config cache

Fail-safe contract: hooks that call this wrap everything in try/except and
exit 0 — a corrupt DB must never break a session. Functions here raise
normally so the selftest and CLI see real errors.

Self-check:  python3 store.py --selftest
"""
import os, re, time, sqlite3

import paths

SCHEMA_VERSION = 1

MIGRATIONS = {
    1: [
        "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)",
        """CREATE TABLE IF NOT EXISTS lessons(
             id INTEGER PRIMARY KEY, ts REAL NOT NULL, text TEXT NOT NULL UNIQUE,
             tags TEXT DEFAULT '', keys TEXT DEFAULT '', kw TEXT DEFAULT '',
             weight REAL DEFAULT 1.0, source TEXT DEFAULT 'manual',
             uses INTEGER DEFAULT 0, last_used REAL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS receipts(
             id INTEGER PRIMARY KEY, ts REAL NOT NULL, session TEXT DEFAULT '',
             skill TEXT NOT NULL, note TEXT DEFAULT '', tokens INTEGER DEFAULT 0,
             project TEXT DEFAULT '')""",
        """CREATE TABLE IF NOT EXISTS routes(
             id INTEGER PRIMARY KEY, ts REAL NOT NULL, session TEXT DEFAULT '',
             cluster TEXT NOT NULL, skill TEXT NOT NULL,
             outcome TEXT DEFAULT 'fired', project TEXT DEFAULT '')""",
        """CREATE TABLE IF NOT EXISTS metrics(
             id INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL,
             value REAL DEFAULT 0, meta TEXT DEFAULT '')""",
        "CREATE INDEX IF NOT EXISTS idx_lessons_ts ON lessons(ts)",
        "CREATE INDEX IF NOT EXISTS idx_receipts_ts ON receipts(ts)",
        "CREATE INDEX IF NOT EXISTS idx_routes_ts ON routes(ts)",
        "CREATE INDEX IF NOT EXISTS idx_routes_cs ON routes(cluster, skill)",
    ],
}


def connect(path: str = "") -> sqlite3.Connection:
    p = path or paths.db_path()
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(p, timeout=0.6)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=600")
    _migrate(conn)
    return conn


def _migrate(conn) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
    cur = int(get_meta(conn, "schema_version", "0"))
    for v in sorted(MIGRATIONS):
        if v > cur:
            for ddl in MIGRATIONS[v]:
                conn.execute(ddl)
            set_meta(conn, "schema_version", str(v))
    conn.commit()


def get_meta(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(conn, key: str, value: str) -> None:
    conn.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()


# ── lessons + recall ─────────────────────────────────────────────────────────
STOP = set("""a about above after again all also am an and any are as at be because been
before being below between both but by can could did do does doing down during each few
for from further had has have having he her here hers him his how i if in into is it its
itself just like me more most my no nor not now of off on once only or other our out over
own please same she should so some still such than thanks that the their theirs them then
there these they this those through to too under until up us very want was we were what
when where which while who whom why will with would you your yours really maybe let lets
gonna going get got make makes need needs thing things way""".split())


def keywords(text: str) -> set:
    """Cheap embedding substitute: content-word tokens, code-ish tokens kept whole."""
    toks = re.findall(r"[a-zA-Z_][a-zA-Z0-9_\-\.]{2,}", (text or "").lower())
    out = set()
    for t in toks:
        t = t.strip(".-_")
        if len(t) >= 3 and t not in STOP:
            out.add(t)
        if len(out) >= 60:
            break
    return out


def add_lesson(conn, text: str, tags: str = "", keys: str = "", weight: float = 1.0,
               source: str = "manual"):
    """Insert a lesson; returns rowid or None (too short / exact duplicate)."""
    text = " ".join((text or "").split())
    if len(text) < 12:
        return None
    kw = " ".join(sorted(keywords(f"{text} {tags} {keys}")))
    cur = conn.execute(
        "INSERT OR IGNORE INTO lessons(ts,text,tags,keys,kw,weight,source) "
        "VALUES(?,?,?,?,?,?,?)", (time.time(), text, tags, keys, kw, weight, source))
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


def recall(conn, text: str, keys: str = "", limit: int = 3):
    """Top past lessons relevant to `text`: keyword overlap × recency × weight,
    with a boost when the lesson was captured in the same project. Empty list
    when nothing clears the relevance bar — silence is a feature."""
    want = keywords(text)
    if len(want) < 2 or limit <= 0:
        return []
    now = time.time()
    scored = []
    for r in conn.execute("SELECT * FROM lessons ORDER BY ts DESC LIMIT 800"):
        kw = set((r["kw"] or "").split())
        ov = len(want & kw)
        if not ov:
            continue
        # exact token match — 'web' must not claim lessons from 'website'
        same_project = bool(keys) and keys in re.split(r"[,\s]+", r["keys"] or "")
        if ov < 2 and not same_project:
            continue
        age_days = max(0.0, (now - r["ts"]) / 86400)
        recency = 0.5 ** (age_days / 45.0)
        score = ov * (0.4 + 0.6 * recency) * (r["weight"] or 1.0) * (1.5 if same_project else 1.0)
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    top = [r for s, r in scored[:limit] if s >= 1.2]
    for r in top:
        conn.execute("UPDATE lessons SET uses=uses+1, last_used=? WHERE id=?", (now, r["id"]))
    if top:
        conn.commit()
    return [dict(r) for r in top]


# ── receipts ─────────────────────────────────────────────────────────────────
def add_receipt(conn, skill: str, note: str, session: str = "", tokens: int = 0,
                project: str = "") -> int:
    cur = conn.execute("INSERT INTO receipts(ts,session,skill,note,tokens,project) "
                       "VALUES(?,?,?,?,?,?)",
                       (time.time(), session, skill, " ".join((note or "").split())[:200],
                        int(tokens or 0), project))
    conn.commit()
    return cur.lastrowid


def recent_receipts(conn, limit: int = 30, days: float = 0):
    q = "SELECT * FROM receipts"
    args = []
    if days:
        q += " WHERE ts > ?"
        args.append(time.time() - days * 86400)
    q += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(q, args)]


# ── routes (adaptive routing substrate) ──────────────────────────────────────
def log_route(conn, cluster: str, skill: str, session: str = "", project: str = "") -> int:
    cur = conn.execute("INSERT INTO routes(ts,session,cluster,skill) VALUES(?,?,?,?)",
                       (time.time(), session, cluster, skill))
    conn.commit()
    return cur.lastrowid


def set_route_outcome(conn, rowid: int, outcome: str) -> None:
    conn.execute("UPDATE routes SET outcome=? WHERE id=?", (outcome, rowid))
    conn.commit()


def route_stats(conn, halflife_days: float = 30.0) -> dict:
    """Decayed per-(cluster,skill) counters. Old evidence fades — a route the
    user stopped overriding months ago gets a clean slate."""
    now = time.time()
    out = {}
    for r in conn.execute("SELECT ts,cluster,skill,outcome FROM routes WHERE ts > ?",
                          (now - 90 * 86400,)):
        w = 0.5 ** ((now - r["ts"]) / 86400.0 / halflife_days)
        d = out.setdefault((r["cluster"], r["skill"]),
                           {"fires": 0.0, "resolved": 0.0, "accepts": 0.0})
        d["fires"] += w
        if r["outcome"] in ("accepted", "overridden", "ignored"):
            d["resolved"] += w
            if r["outcome"] == "accepted":
                d["accepts"] += w
    return out


# ── metrics + counts ─────────────────────────────────────────────────────────
def add_metric(conn, kind: str, value: float = 0, meta: str = "") -> None:
    conn.execute("INSERT INTO metrics(ts,kind,value,meta) VALUES(?,?,?,?)",
                 (time.time(), kind, value, meta))
    conn.commit()


def counts(conn) -> dict:
    out = {}
    for t in ("lessons", "receipts", "routes", "metrics"):
        out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out


def selftest() -> int:
    import tempfile
    p = os.path.join(tempfile.mkdtemp(prefix="pantheon-store-"), "t.db")
    conn = connect(p)
    conn2 = connect(p)  # migration idempotent, WAL allows a second handle
    assert get_meta(conn, "schema_version") == str(SCHEMA_VERSION)
    # lessons: insert, dedupe, too-short
    lid = add_lesson(conn, "X.com DM bubbles: direction comes ONLY from the bg-class, "
                           "never justify-end", tags="correction", keys="parserx")
    assert lid and add_lesson(conn, "X.com DM bubbles: direction comes ONLY from the "
                                    "bg-class, never justify-end") is None
    assert add_lesson(conn, "too short") is None
    add_lesson(conn, "deploy via scp plus pm2 reload, git pull aborts on the vps",
               keys="parserx")
    # recall: relevant hit, irrelevant miss, project boost, uses bump
    hits = recall(conn, "why is the DM bubble direction wrong on x.com?", keys="parserx")
    assert hits and "bg-class" in hits[0]["text"], hits
    assert recall(conn, "bake a chocolate cake tonight") == []
    # project boost is exact-token: 'parser' must not substring-match 'parserx'
    one_kw = recall(conn, "the direction of the wind tonight", keys="parser")
    assert all("parserx" != l for h in one_kw for l in [h["keys"]]) or one_kw == []
    assert conn.execute("SELECT uses FROM lessons WHERE id=?", (lid,)).fetchone()[0] == 1
    assert len(keywords("Fix the hud.py effort segment ASAP")) >= 3
    # receipts
    add_receipt(conn, "hydra", "root-caused the chrome leak,  reaped   stale procs",
                session="s1", tokens=1200, project="parserx")
    rs = recent_receipts(conn, days=1)
    assert rs and rs[0]["skill"] == "hydra" and "  " not in rs[0]["note"]
    # routes: fire → outcome → decayed stats
    rid = log_route(conn, "hydra", "hydra", session="s1")
    set_route_outcome(conn, rid, "accepted")
    log_route(conn, "hydra", "hydra", session="s1")  # unresolved fire
    st = route_stats(conn)
    d = st[("hydra", "hydra")]
    assert d["fires"] > 1.9 and d["accepts"] > 0.9 and d["resolved"] < d["fires"]
    add_metric(conn, "gate_block", 1, "tests failed")
    c = counts(conn)
    assert c["lessons"] == 2 and c["receipts"] == 1 and c["routes"] == 2 and c["metrics"] == 1
    conn.close(); conn2.close()
    print("selftest ok — schema v%s, recall + receipts + routes + metrics" % SCHEMA_VERSION)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
