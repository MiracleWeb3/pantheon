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

OK, WARN, BAD = "✓", "⚠", "✗"

SELFTEST_MODULES = ["lib/paths.py", "lib/config.py", "lib/store.py", "lib/transcript.py",
                    "hooks/on_prompt.py", "hooks/on_stop.py", "hooks/session-start.py",
                    "scripts/cli.py", "scripts/dashboard.py", "scripts/hud.py"]


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
    try:
        conn = store.connect(p)
        ok = conn.execute("PRAGMA quick_check").fetchone()[0]
        c = store.counts(conn)
        ver = store.get_meta(conn, "schema_version")
        conn.close()
        if ok == "ok":
            return OK, (f"store ok — schema v{ver}, {c['lessons']} lessons, "
                        f"{c['receipts']} receipts, {c['routes']} routes")
        detail = ok
    except Exception as e:
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
    names, dups, unnamed = {}, [], 0
    try:
        entries = sorted(os.listdir(root))
    except Exception:
        return BAD, "skills/ directory missing"
    for d in entries:
        p = os.path.join(root, d, "SKILL.md")
        if not os.path.isfile(p):
            continue
        try:
            head = "".join(open(p, encoding="utf-8", errors="replace").readlines()[:12])
        except Exception:
            unnamed += 1
            continue
        m = re.search(r"^name:\s*[\"']?([\w.-]+)", head, re.M)
        if not m:
            unnamed += 1
            continue
        n = m.group(1)
        if n in names:
            dups.append(n)
        names[n] = d
    if dups or unnamed:
        shown = ", ".join(sorted(set(dups))[:8])
        more = "…" if len(set(dups)) > 8 else ""
        return WARN, (f"{len(names)} skills; duplicate names: {shown}{more}"
                      + (f"; {unnamed} without a name" if unnamed else ""))
    return OK, f"{len(names)} skills, no duplicate names"


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
              check_state_files(), check_selftests()]
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
    print("selftest ok — db corrupt/rebuild, skill dup scan, hooks wiring")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(run_all(fix="--fix" in sys.argv))
