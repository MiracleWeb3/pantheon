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
import os, re, time, math, sqlite3

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
    """Top past lessons relevant to `text`, BM25-ranked (IDF-weighted, length-
    normalized — a rare shared term like 'kubeconfig' outweighs three shared
    'deploy's, and a keyword-stuffed lesson stops winning on breadth), then
    shaped by recency × weight × same-project boost. Empty list when nothing
    clears the relevance bar — silence is a feature. Pure stdlib, two passes
    over the recent-800 window (collect docs, then score)."""
    want = keywords(text)
    if len(want) < 2 or limit <= 0:
        return []
    now = time.time()
    rows = [(r, set((r["kw"] or "").split()))
            for r in conn.execute("SELECT * FROM lessons ORDER BY ts DESC LIMIT 800")]
    if not rows:
        return []
    n_docs = len(rows)
    avgdl = sum(len(kw) for _, kw in rows) / n_docs or 1.0
    df = {t: sum(1 for _, kw in rows if t in kw) for t in want}
    idf = {t: math.log((n_docs - df[t] + 0.5) / (df[t] + 0.5) + 1.0)
           for t in want if df[t]}
    K1, B = 1.5, 0.75  # term freq is 1 (kw is a set), so BM25 reduces to
    scored = []        # Σ idf(t) · (K1+1)/(1 + K1·lennorm)
    for r, kw in rows:
        hit = want & kw
        ov = len(hit)
        if not ov:
            continue
        # exact token match — 'web' must not claim lessons from 'website'
        same_project = bool(keys) and keys in re.split(r"[,\s]+", r["keys"] or "")
        if ov < 2 and not same_project:
            continue
        if (r["source"] or "") == "pack" and not same_project:
            continue  # pack lessons never leave the repo that shipped them
        if (r["source"] or "") == "auto" and ov < 2:
            continue  # auto-captured text needs 2+ shared keywords to resurface
        lennorm = 1.0 - B + B * (len(kw) / avgdl)
        bm25 = sum(idf.get(t, 0.0) * (K1 + 1) / (1 + K1 * lennorm) for t in hit)
        age_days = max(0.0, (now - r["ts"]) / 86400)
        recency = 0.5 ** (age_days / 45.0)
        score = bm25 * (0.4 + 0.6 * recency) * (r["weight"] or 1.0) * (1.5 if same_project else 1.0)
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
RETENTION_DAYS = {"routes": 90, "metrics": 90, "receipts": 180, "lessons_auto": 90}


def prune(conn, now: float = 0) -> dict:
    """Retention sweep so the store never grows forever: old routes/metrics/
    receipts out; auto-captured lessons that were never recalled aged out.
    Manual and pack lessons are kept — they were deliberate. Returns per-table
    delete counts; VACUUMs only after a meaningful shrink."""
    now = now or time.time()
    out = {
        "routes": conn.execute("DELETE FROM routes WHERE ts<?",
                               (now - RETENTION_DAYS["routes"] * 86400,)).rowcount,
        "metrics": conn.execute("DELETE FROM metrics WHERE ts<?",
                                (now - RETENTION_DAYS["metrics"] * 86400,)).rowcount,
        "receipts": conn.execute("DELETE FROM receipts WHERE ts<?",
                                 (now - RETENTION_DAYS["receipts"] * 86400,)).rowcount,
        "lessons": conn.execute(
            "DELETE FROM lessons WHERE source='auto' AND uses=0 AND ts<?",
            (now - RETENTION_DAYS["lessons_auto"] * 86400,)).rowcount,
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
    assert route_stats(conn, only=("hydra", "hydra"))[("hydra", "hydra")]["fires"] > 1.9
    assert route_stats(conn, only=("nope", "nope")) == {}
    add_metric(conn, "gate_block", 1, "tests failed")
    c = counts(conn)
    assert c["lessons"] == 2 and c["receipts"] == 1 and c["routes"] == 2 and c["metrics"] == 1
    # pack lessons are quarantined to the project that shipped them
    add_lesson(conn, "pack lesson: the deploy pipeline requires manual approval gate",
               keys="packproj", source="pack")
    assert recall(conn, "how does the deploy pipeline approval work?", keys="otherproj") == []
    hits = recall(conn, "how does the deploy pipeline approval work?", keys="packproj")
    assert hits and hits[0]["source"] == "pack"
    # BM25: a rare shared term beats common ones — six lessons share 'deploy',
    # only one also carries 'kubeconfig'; a query with both must rank it first
    for i in range(5):
        add_lesson(conn, f"deploy note number {i}: remember the deploy checklist step {i}",
                   keys="bmproj")
    add_lesson(conn, "deploy tip: the kubeconfig context must be set before rollout",
               keys="bmproj")
    bm_hits = recall(conn, "deploy fails — is the kubeconfig context wrong?", keys="bmproj")
    assert bm_hits and "kubeconfig" in bm_hits[0]["text"], bm_hits
    # auto-captured lessons need >=2 shared keywords even in their own project
    add_lesson(conn, "auto captured: you keep forgetting pm2 reload for deploys",
               keys="parserx", source="auto")
    assert all(h["source"] != "auto"
               for h in recall(conn, "the deploys tonight look fine honestly", keys="parserx"))
    assert any(h["source"] == "auto"
               for h in recall(conn, "why is pm2 reload for deploys broken?", keys="parserx"))
    # prune: stale operational rows and never-recalled auto lessons go;
    # deliberate (manual/pack) lessons stay
    stale = time.time() - 200 * 86400
    conn.execute("UPDATE routes SET ts=?", (stale,))
    conn.execute("INSERT INTO lessons(ts,text,source) VALUES(?,?,'auto')",
                 (stale, "stale auto lesson that nobody ever recalled once"))
    conn.commit()
    pr = prune(conn)
    assert pr["routes"] == 2 and pr["lessons"] == 1, pr
    assert get_meta(conn, "last_prune")
    assert conn.execute("SELECT COUNT(*) FROM lessons WHERE source='manual'").fetchone()[0] == 8
    conn.close(); conn2.close()
    print("selftest ok — schema v%s, recall + receipts + routes + metrics" % SCHEMA_VERSION)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
