#!/usr/bin/env python3
"""pantheon store — one SQLite substrate under every feature.

~/.claude/pantheon/pantheon.db (WAL, stdlib sqlite3, created on demand,
schema versioned in `meta`). Four tables:

  receipts  per-discipline action log: skill, note, tokens, timestamp
  routes    router fires and their outcome (accepted/overridden/ignored)
  metrics   loose rollups (gate blocks, doctor runs, ...)
  meta      schema version, pack-import markers, config cache

Memory is deliberately NOT here. claude-memory-light indexes every transcript
verbatim and answers recall questions better than a lesson table ever did;
pantheon shouldn't run a second, worse copy. Databases created before v3.0 keep
an orphan `lessons` table — harmless, never read, left alone rather than dropped
so nothing captured is destroyed on upgrade.

Fail-safe contract: hooks that call this wrap everything in try/except and
exit 0 — a corrupt DB must never break a session. Functions here raise
normally so the selftest and CLI see real errors.

Self-check:  python3 store.py --selftest
"""
import os, time, sqlite3

import paths

SCHEMA_VERSION = 1

MIGRATIONS = {
    1: [
        "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)",
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
    conn = sqlite3.connect(p, timeout=3.0)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")  # concurrent sessions: wait, don't drop writes
        _migrate(conn)
        return conn
    except Exception:
        conn.close()  # Windows can't rename/delete a file with a handle still open on it
        raise


def _migrate(conn) -> None:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row and int(row[0]) == SCHEMA_VERSION:
            return  # fast path — connect() runs on every prompt; no DDL, no write txn
        cur = int(row[0]) if row else 0
    except Exception:
        cur = 0
    conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
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


def route_stats(conn, halflife_days: float = 30.0, only: tuple = None) -> dict:
    """Decayed per-(cluster,skill) counters. Old evidence fades — a route the
    user stopped overriding months ago gets a clean slate. `only=(cluster,
    skill)` narrows the scan for the per-prompt hot path."""
    now = time.time()
    out = {}
    q, args = "SELECT ts,cluster,skill,outcome FROM routes WHERE ts > ?", [now - 90 * 86400]
    if only:
        q += " AND cluster=? AND skill=?"
        args += [only[0], only[1]]
    for r in conn.execute(q, args):
        w = 0.5 ** ((now - r["ts"]) / 86400.0 / halflife_days)
        d = out.setdefault((r["cluster"], r["skill"]),
                           {"fires": 0.0, "resolved": 0.0, "accepts": 0.0})
        d["fires"] += w
        if r["outcome"] in ("accepted", "overridden", "ignored"):
            d["resolved"] += w
            if r["outcome"] == "accepted":
                d["accepts"] += w
    return out


# ── retention ────────────────────────────────────────────────────────────────
RETENTION_DAYS = {"routes": 90, "metrics": 90, "receipts": 180}


def prune(conn, now: float = 0) -> dict:
    """Retention sweep so the store never grows forever: old routes, metrics
    and receipts out. Returns per-table delete counts; VACUUMs only after a
    meaningful shrink."""
    now = now or time.time()
    out = {
        "routes": conn.execute("DELETE FROM routes WHERE ts<?",
                               (now - RETENTION_DAYS["routes"] * 86400,)).rowcount,
        "metrics": conn.execute("DELETE FROM metrics WHERE ts<?",
                                (now - RETENTION_DAYS["metrics"] * 86400,)).rowcount,
        "receipts": conn.execute("DELETE FROM receipts WHERE ts<?",
                                 (now - RETENTION_DAYS["receipts"] * 86400,)).rowcount,
    }
    conn.commit()
    set_meta(conn, "last_prune", str(int(now)))
    if sum(out.values()) >= 500:
        try:
            conn.execute("VACUUM")
        except Exception:
            pass
    return out


# ── metrics + counts ─────────────────────────────────────────────────────────
def add_metric(conn, kind: str, value: float = 0, meta: str = "") -> None:
    conn.execute("INSERT INTO metrics(ts,kind,value,meta) VALUES(?,?,?,?)",
                 (time.time(), kind, value, meta))
    conn.commit()


def counts(conn) -> dict:
    out = {}
    for t in ("receipts", "routes", "metrics"):
        out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out


def selftest() -> int:
    import tempfile
    p = os.path.join(tempfile.mkdtemp(prefix="pantheon-store-"), "t.db")
    conn = connect(p)
    conn2 = connect(p)  # migration idempotent, WAL allows a second handle
    assert get_meta(conn, "schema_version") == str(SCHEMA_VERSION)
    # memory lives in claude-memory-light now — this store must not grow it back
    assert "add_lesson" not in globals() and "recall" not in globals()
    assert "lessons" not in " ".join(sum(MIGRATIONS.values(), []))
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
    assert route_stats(conn, only=("hydra", "hydra"))[("hydra", "hydra")]["fires"] > 1.9
    assert route_stats(conn, only=("nope", "nope")) == {}
    add_metric(conn, "gate_block", 1, "tests failed")
    c = counts(conn)
    assert c == {"receipts": 1, "routes": 2, "metrics": 1}, c
    # an upgraded DB keeps its orphan lessons table — untouched, never counted
    conn.execute("CREATE TABLE lessons(id INTEGER PRIMARY KEY, text TEXT)")
    conn.execute("INSERT INTO lessons(text) VALUES('a pre-v2.1 capture')")
    conn.commit()
    assert "lessons" not in counts(conn)
    # prune: stale operational rows go, and the orphan table is left alone
    stale = time.time() - 200 * 86400
    conn.execute("UPDATE routes SET ts=?", (stale,))
    conn.commit()
    pr = prune(conn)
    assert pr == {"routes": 2, "metrics": 0, "receipts": 0}, pr
    assert get_meta(conn, "last_prune")
    assert conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 1
    conn.close(); conn2.close()
    print("selftest ok — schema v%s, receipts + routes + metrics (no memory)" % SCHEMA_VERSION)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
