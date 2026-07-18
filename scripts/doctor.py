#!/usr/bin/env python3
"""pantheon doctor — diagnose the install, fix what's fixable.

Checks: python, hooks wiring, all module selftests, config validity, store
integrity (+ rebuild), spend-ledger health (+ prune), CLI shim (+ rewrite),
duplicate skill names, runtime state files. `--fix` applies the safe fixes;
nothing destructive happens without it, and the corrupt DB is always backed
up, never deleted.

Exit code: 0 = healthy (warnings allowed), 1 = at least one ✗.
Self-check: python3 doctor.py --selftest
"""
import sys, os, json, re, time, subprocess, importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lib"))
import store, paths
import config as cfgmod
import transcript as trmod

OK, WARN, BAD = "✓", "⚠", "✗"

SELFTEST_MODULES = ["lib/paths.py", "lib/config.py", "lib/store.py", "lib/transcript.py",
                    "lib/limits.py",
                    "hooks/on_prompt.py", "hooks/on_stop.py", "hooks/session-start.py",
                    "scripts/cli.py", "scripts/dashboard.py", "scripts/hud.py",
                    "scripts/mcp_server.py"]


def check_python():
    v = sys.version_info
    if v < (3, 8):
        return BAD, f"python {sys.version.split()[0]} — need 3.8+"
    return OK, f"python {sys.version.split()[0]}"


def check_hooks():
    p = os.path.join(_ROOT, "hooks", "hooks.json")
    try:
        h = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        return BAD, f"hooks.json unreadable: {e}"
    missing = []
    for ev, arr in h.get("hooks", {}).items():
        for grp in arr if isinstance(arr, list) else []:
            for cmd in grp.get("hooks", []):
                m = re.search(r"/hooks/([\w.-]+\.py)", cmd.get("command", ""))
                if m and not os.path.isfile(os.path.join(_ROOT, "hooks", m.group(1))):
                    missing.append(m.group(1))
    if missing:
        return BAD, "hook files missing: " + ", ".join(missing)
    return OK, "hooks wired: " + ", ".join(h.get("hooks", {}))


def check_selftests():
    fails = []
    for m in SELFTEST_MODULES:
        try:
            r = subprocess.run([sys.executable, os.path.join(_ROOT, m), "--selftest"],
                               capture_output=True, timeout=30)
            if r.returncode != 0:
                fails.append(m)
        except Exception:
            fails.append(m)
    if fails:
        return BAD, "selftests FAILING: " + ", ".join(fails)
    return OK, f"{len(SELFTEST_MODULES)} module selftests pass"


def check_config():
    warns = []
    for scope, p in (("global", os.path.join(os.path.expanduser("~"), ".claude",
                                             "pantheon", "config.json")),
                     ("project", os.path.join(os.getcwd(), ".pantheon", "config.json"))):
        if not os.path.isfile(p):
            continue
        try:
            raw = json.load(open(p, encoding="utf-8"))
        except Exception:
            warns.append(f"{scope} config unparseable (falls back to defaults)")
            continue
        warns += [f"{scope}: {w}" for w in cfgmod.validate(raw)]
    if warns:
        return WARN, "; ".join(warns)
    return OK, f"config resolves (preset: {cfgmod.load(os.getcwd())['preset']})"


def check_db(path: str = "", fix: bool = False):
    p = path or paths.db_path()
    if not os.path.isfile(p):
        return OK, "store not created yet (appears on first use)"
    conn = None
    try:
        conn = store.connect(p)
        ok = conn.execute("PRAGMA quick_check").fetchone()[0]
        c = store.counts(conn)
        ver = store.get_meta(conn, "schema_version")
        if ok == "ok":
            if fix:
                n = sum(store.prune(conn).values())
                tail = f", pruned {n} old row(s)" if n else ", nothing to prune"
            else:
                last = float(store.get_meta(conn, "last_prune", "0") or 0)
                tail = f", last prune {int((time.time() - last) / 86400)}d ago" if last else ""
            conn.close()
            mb = os.path.getsize(p) / 1e6
            return OK, (f"store ok — schema v{ver}, {c['lessons']} lessons, "
                        f"{c['receipts']} receipts, {c['routes']} routes "
                        f"({mb:.1f} MB{tail})")
        conn.close()
        detail = ok
    except Exception as e:
        if conn:
            try:
                conn.close()  # else the rename below hits a locked file on Windows
            except Exception:
                pass
        detail = str(e)[:80]
    if fix:
        bak = p + ".corrupt-" + time.strftime("%Y%m%d%H%M%S")
        try:
            os.rename(p, bak)
            for suffix in ("-wal", "-shm"):
                if os.path.isfile(p + suffix):
                    os.rename(p + suffix, bak + suffix)
            store.connect(p).close()
            return WARN, f"store was corrupt → rebuilt fresh (old file kept: {os.path.basename(bak)})"
        except Exception as e:
            return BAD, f"store corrupt and rebuild failed: {e}"
    return BAD, f"store corrupt ({detail}) — `pantheon doctor --fix` rebuilds it (old file is backed up)"


def check_ledger(fix: bool = False):
    p = os.path.join(paths.state_dir(), "usage-events.jsonl")
    if not os.path.isfile(p):
        return OK, "spend ledger not started yet (HUD writes it)"
    good, bad = [], 0
    for ln in open(p, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(ln)
            float(e["d"])
            good.append(ln)
        except Exception:
            bad += 1
    size_mb = os.path.getsize(p) / 1e6
    if (bad or size_mb > 5) and fix:
        with open(p, "w", encoding="utf-8") as f:
            f.writelines(good[-5000:])
        return OK, f"ledger cleaned ({bad} bad lines dropped, kept last {min(len(good), 5000)})"
    if bad:
        return WARN, f"ledger has {bad} bad line(s) — --fix prunes them"
    if size_mb > 5:
        return WARN, f"ledger is {size_mb:.1f} MB — --fix prunes to the last 5000 events"
    return OK, f"spend ledger ok ({len(good)} events)"


def _session_start_module():
    spec = importlib.util.spec_from_file_location(
        "pantheon_session_start", os.path.join(_ROOT, "hooks", "session-start.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def check_shim(fix: bool = False):
    p = paths.shim_path()
    want = os.path.join(_ROOT, "scripts", "cli.py")
    try:
        if os.path.isfile(p) and want in open(p, encoding="utf-8").read():
            return OK, "CLI shim points at this install"
    except Exception:
        pass
    if fix:
        try:
            if _session_start_module().write_shim(_ROOT, p):
                return OK, "CLI shim rewritten"
        except Exception:
            pass
    return WARN, "CLI shim stale or missing — next SessionStart rewrites it (or --fix now)"


def check_skills(root: str = ""):
    root = root or os.path.join(_ROOT, "skills")
    names, dups, unnamed, desc_bytes = {}, [], 0, 0
    try:
        entries = sorted(os.listdir(root))
    except Exception:
        return BAD, "skills/ directory missing"
    for d in entries:
        p = os.path.join(root, d, "SKILL.md")
        if not os.path.isfile(p):
            continue
        try:
            head = open(p, encoding="utf-8", errors="replace").read(4000)
        except Exception:
            unnamed += 1
            continue
        m = re.search(r"^name:\s*[\"']?([\w.-]+)", head, re.M)
        dm = re.search(r"^description:\s*(.+?)(?=^[\w-]+:|^---)", head, re.M | re.S)
        if dm:  # Claude Code loads every skill's description into each session
            desc_bytes += len(dm.group(1))
        if not m:
            unnamed += 1
            continue
        n = m.group(1)
        if n in names:
            dups.append(n)
        names[n] = d
    overhead = f" (≈{desc_bytes / 4 / 1000:.1f}k tokens of listings per session)"
    if dups or unnamed:
        shown = ", ".join(sorted(set(dups))[:8])
        more = "…" if len(set(dups)) > 8 else ""
        return WARN, (f"{len(names)} skills; duplicate names: {shown}{more}"
                      + (f"; {unnamed} without a name" if unnamed else ""))
    # Every router target must be a discipline that exists. Renaming a skill and
    # leaving the router pointing at the old name routes prompts into nothing, and
    # nothing else here notices -- names and duplicates both look fine.
    dead = _dead_router_targets(os.path.dirname(root))  # root is <base>/skills by now
    if dead:
        return WARN, (f"{len(names)} skills, but the router points at "
                      f"{len(dead)} that do not exist: {', '.join(sorted(dead))}")
    return OK, f"{len(names)} skills, no duplicate names{overhead}"


def _dead_router_targets(root: str = ""):
    base = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        src = open(os.path.join(base, "hooks", "on_prompt.py"), encoding="utf-8").read()
    except OSError:
        return []
    targets = re.findall(r'^\s*\("([a-z0-9-]+)",\s*r?"', src, re.M)
    skills_dir = os.path.join(base, "skills")
    have = {d for d in os.listdir(skills_dir)} if os.path.isdir(skills_dir) else set()
    return [t for t in targets if t not in have]


def check_transcript_format(projects_dir: str = ""):
    """CC-format-drift tripwire: if the newest real transcripts all yield an
    empty turn digest, the transcript shape changed and gate / receipts /
    derived meters are silently blind — surface it instead of dying quiet."""
    root = projects_dir or os.path.join(os.path.expanduser("~"), ".claude", "projects")
    cands = []
    try:
        for base, _d, fns in os.walk(root):
            for fn in fns:
                if fn.endswith(".jsonl"):
                    p = os.path.join(base, fn)
                    try:
                        st = os.stat(p)
                    except Exception:
                        continue
                    if st.st_size >= 4096:
                        cands.append((st.st_mtime, p))
    except Exception:
        pass
    if not cands:
        return OK, "no transcripts to check (fresh install)"
    for _, p in sorted(cands, reverse=True)[:3]:
        try:
            t = trmod.scan_turn(p)
        except Exception:
            continue
        if t.get("last_user") or t.get("edits") or t.get("skills") or t.get("out_tokens"):
            return OK, "transcript format recognized (turn digest parses)"
    return WARN, ("transcript format UNRECOGNIZED in the newest sessions — Claude Code "
                  "may have changed its JSONL; the gate/receipts/meters may be blind. "
                  "Check for a pantheon update.")


def check_state_files():
    bad = []
    d = paths.state_dir()
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        try:
            json.load(open(os.path.join(d, fn), encoding="utf-8"))
        except Exception:
            bad.append(fn)
    if bad:
        return WARN, "unparseable state files (safe to delete): " + ", ".join(bad)
    return OK, "runtime state files parse"


def run_all(fix: bool = False) -> int:
    try:
        with open(os.path.join(_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            ver = json.load(f).get("version", "?")
    except Exception:
        ver = "?"
    print(f"pantheon doctor — v{ver} @ {_ROOT}" + ("  (--fix)" if fix else ""))
    checks = [check_python(), check_hooks(), check_config(), check_db(fix=fix),
              check_ledger(fix=fix), check_shim(fix=fix), check_skills(),
              check_state_files(), check_transcript_format(), check_selftests()]
    bad = warn = 0
    for status, msg in checks:
        print(f" {status} {msg}")
        bad += status == BAD
        warn += status == WARN
    if bad:
        print(f"{bad} failing check(s), {warn} warning(s)" +
              ("" if fix else " — some may be fixable with --fix"))
    elif warn:
        print(f"healthy with {warn} warning(s)")
    else:
        print("all healthy")
    try:
        conn = store.connect()
        store.add_metric(conn, "doctor_run", bad + warn, f"bad={bad} warn={warn}")
        conn.close()
    except Exception:
        pass
    return 1 if bad else 0


def selftest() -> int:
    import tempfile
    d = tempfile.mkdtemp(prefix="pantheon-doc-")
    # corrupt db → BAD, then --fix rebuilds and backs up
    p = os.path.join(d, "x.db")
    open(p, "w").write("this is not sqlite at all, sorry")
    s, msg = check_db(p)
    assert s == BAD and "corrupt" in msg, (s, msg)
    s, msg = check_db(p, fix=True)
    assert s == WARN and "rebuilt" in msg
    assert any(f.startswith("x.db.corrupt-") for f in os.listdir(d))
    s, _ = check_db(p)
    assert s == OK  # the rebuilt store is healthy
    # duplicate skill names → WARN; clean set → OK
    for name, folder in (("alpha", "a"), ("alpha", "b"), ("beta", "c")):
        os.makedirs(os.path.join(d, "sk", folder), exist_ok=True)
        open(os.path.join(d, "sk", folder, "SKILL.md"), "w").write(
            f"---\nname: {name}\ndescription: x\n---\n")
    s, msg = check_skills(os.path.join(d, "sk"))
    assert s == WARN and "alpha" in msg
    os.remove(os.path.join(d, "sk", "b", "SKILL.md"))
    s, msg = check_skills(os.path.join(d, "sk"))
    assert s == OK and "2 skills" in msg
    # hooks + python + config on the real tree
    assert check_python()[0] == OK
    assert check_hooks()[0] == OK, check_hooks()
    # transcript drift tripwire: empty dir OK, valid digest OK, garbage WARNs
    td = os.path.join(d, "projects", "p1")
    os.makedirs(td)
    assert check_transcript_format(os.path.join(d, "projects"))[0] == OK
    good = json.dumps({"type": "user", "message": {"content": "fix the parser bug"}})
    open(os.path.join(td, "s.jsonl"), "w").write((good + "\n") * 200)
    s, msg = check_transcript_format(os.path.join(d, "projects"))
    assert s == OK and "recognized" in msg, (s, msg)
    open(os.path.join(td, "s.jsonl"), "w").write('{"totally": "unknown-shape"}\n' * 200)
    s, msg = check_transcript_format(os.path.join(d, "projects"))
    assert s == WARN and "UNRECOGNIZED" in msg, (s, msg)
    print("selftest ok — db corrupt/rebuild, skill dup scan, hooks wiring, drift tripwire")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(run_all(fix="--fix" in sys.argv))
