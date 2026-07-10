#!/usr/bin/env python3
"""pantheon SessionStart hook — config directive, store migration, CLI shim,
update check.

Five quiet jobs at session start:
  1. CONFIG DIRECTIVE — inject one short line when config is non-default
     (economy/quiet/custom); completely silent on default "full" (0 tokens).
  2. STORE — open the SQLite store so schema migrations run before anything
     else touches it this session.
  3. SHIM — (re)write ~/.claude/pantheon/bin/pantheon pointing at the
     currently-installed plugin root, so skills and the user always have a
     stable `pantheon` command no matter where the plugin version lives.
  4. TEAM PACK — when the repo carries a pantheon.pack.json: import its shared
     lessons into the store (once per content hash) and inject its standards.
  5. UPDATE CHECK — daily, 2s timeout, fail-silent, cacheable, opt-out.

Fail-silent. Self-check: python3 session-start.py --selftest
"""
import sys, os, json, datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "lib"))
try:
    import config as _config
    import store as _store
    import paths as _paths
except Exception:
    _config = _store = _paths = None


def directive(cfg: dict) -> str:
    """One short line describing non-default config, or '' when default."""
    bits = []
    if not cfg.get("announce", True):
        bits.append("skip the announce block")
    routing = cfg.get("routing", "on")
    if routing == "off":
        bits.append("auto-routing is OFF — the user invokes skills explicitly")
    elif routing == "suggest":
        bits.append("route only on a strong, confident match")
    if not cfg.get("receipts", True):
        bits.append("skip receipt filing")
    disabled = [k for k, v in cfg.get("disciplines", {}).items() if not v]
    always = "keep all prose terse and token-frugal" if not cfg.get("announce", True) else ""

    if not bits and not disabled and not always:
        return ""  # default experience — say nothing, spend nothing

    parts = [f"[PANTHEON CONFIG · {cfg.get('preset', 'custom')}]"]
    if bits:
        parts.append("For every pantheon skill this session: " + "; ".join(bits) + ".")
    if always:
        parts.append(always.capitalize() + ".")
    if disabled:
        parts.append("Disabled disciplines (do not auto-use): " + ", ".join(sorted(disabled)) + ".")
    return " ".join(parts)


def ensure_store() -> None:
    """Open the store once so migrations run at a calm moment."""
    if _store:
        _store.connect().close()


SHIM_TEMPLATE = """#!/bin/sh
# pantheon CLI shim — auto-refreshed each SessionStart; do not edit.
exec python3 "{root}/scripts/cli.py" "$@"
"""


def write_shim(root: str = "", shim_path: str = "") -> bool:
    """Point the stable `pantheon` command at the current plugin root."""
    root = root or os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if not root or not os.path.isfile(os.path.join(root, "scripts", "cli.py")):
        return False
    p = shim_path or (_paths.shim_path() if _paths else "")
    if not p:
        return False
    content = SHIM_TEMPLATE.format(root=root)
    try:
        if os.path.isfile(p) and open(p, encoding="utf-8").read() == content:
            return True
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(p, 0o755)
        return True
    except Exception:
        return False


def import_pack(cwd: str, conn=None) -> str:
    """Merge a team pack's lessons into the store (once per content hash) and
    return its standards as a context line ('' when none)."""
    if not _config or not _store:
        return ""
    path, pk = _config.find_pack(cwd)
    if not pk:
        return ""
    import hashlib
    h = hashlib.md5(json.dumps(pk, sort_keys=True).encode()).hexdigest()[:10]
    own = conn is None
    if own:
        conn = _store.connect()
    try:
        done = _store.get_meta(conn, "packs_imported", "")
        if h not in done.split(","):
            for l in pk.get("lessons", [])[:100]:
                if isinstance(l, dict) and l.get("text"):
                    try:
                        w = float(l.get("weight", 1.1))
                    except Exception:
                        w = 1.1
                    _store.add_lesson(conn, str(l["text"]), tags=str(l.get("tags", "")),
                                      keys=str(l.get("keys", "")), weight=w, source="pack")
            _store.set_meta(conn, "packs_imported", (done + "," + h).strip(","))
    finally:
        if own:
            conn.close()
    std = str(pk.get("standards") or "").strip()
    if std:
        name = pk.get("name") or os.path.basename(os.path.dirname(path))
        return (f"[PANTHEON PACK · {name}] Team standards — follow them this "
                f"session: {std[:1500]}")
    return ""


RAW_MANIFEST = "https://raw.githubusercontent.com/MiracleWeb3/pantheon/main/.claude-plugin/plugin.json"
CHECK_EVERY_HOURS = 24


def _semver(v: str):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return ()


def _newer(latest: str, installed: str) -> bool:
    a, b = _semver(latest), _semver(installed)
    return bool(a and b and a > b)


def check_update(cfg: dict) -> str:
    """One line when a newer version exists; '' otherwise. Networks at most
    once per CHECK_EVERY_HOURS, 2s timeout, fail-silent (offline = silence)."""
    if not cfg.get("updateCheck", True):
        return ""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            installed = json.load(f).get("version", "")
    except Exception:
        return ""
    cache_dir = os.path.join(os.path.expanduser("~"), ".claude", "pantheon")
    cache_p = os.path.join(cache_dir, "update-check.json")
    latest, now = None, datetime.datetime.now()
    try:
        with open(cache_p, encoding="utf-8") as f:
            c = json.load(f)
        if (now - datetime.datetime.fromisoformat(c["at"])).total_seconds() < CHECK_EVERY_HOURS * 3600:
            latest = c.get("latest")
    except Exception:
        pass
    if latest is None:
        try:
            import urllib.request
            with urllib.request.urlopen(RAW_MANIFEST, timeout=2) as r:
                latest = json.loads(r.read().decode()).get("version", "")
        except Exception:
            latest = ""  # offline / rate-limited — cache the miss, stay quiet
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_p, "w", encoding="utf-8") as f:
                json.dump({"at": now.isoformat(), "latest": latest}, f)
        except Exception:
            pass
    if latest and _newer(latest, installed):
        return (f"[PANTHEON UPDATE] v{latest} is available (installed: v{installed}). "
                f"Tell the user in one short line at the start of your reply; to update: "
                f"`claude plugin update pantheon@pantheon` + restart. "
                f"(Disable this check: \"updateCheck\": false in ~/.claude/pantheon/config.json)")
    return ""


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd") or os.getcwd()
    cfg = _config.load(cwd) if _config else {"routing": "on", "announce": True, "preset": "full"}
    try:
        ensure_store()
    except Exception:
        pass
    try:
        write_shim()
    except Exception:
        pass
    line = directive(cfg)
    if line:
        print(line)
    try:
        pack_line = import_pack(cwd)
        if pack_line:
            print(pack_line)
    except Exception:
        pass
    upd = check_update(cfg)
    if upd:
        print(upd)
    return 0


def selftest() -> int:
    assert directive({"routing": "on", "announce": True, "preset": "full",
                      "disciplines": {}, "receipts": True}) == ""
    econ = directive({"routing": "suggest", "announce": False, "preset": "economy",
                      "disciplines": {}, "receipts": True})
    assert "economy" in econ and "announce" in econ and "terse" in econ
    quiet = directive({"routing": "off", "announce": False, "preset": "quiet",
                       "disciplines": {}, "receipts": False})
    assert "OFF" in quiet and "receipt" in quiet
    dis = directive({"routing": "on", "announce": True, "preset": "custom",
                     "disciplines": {"athena": False}, "receipts": True})
    assert "athena" in dis
    # shim: writes against a fake root, idempotent second call, refuses junk root
    import tempfile
    root = os.path.dirname(_HERE)
    p = os.path.join(tempfile.mkdtemp(prefix="pantheon-shim-"), "pantheon")
    assert write_shim(root, p) and os.access(p, os.X_OK)
    assert f'"{root}/scripts/cli.py"' in open(p, encoding="utf-8").read()
    assert write_shim(root, p)  # unchanged content path
    assert not write_shim("/nonexistent-root", p)
    # team pack: lessons import once per hash, standards line comes back
    if _store and _config:
        import tempfile
        d = tempfile.mkdtemp(prefix="pantheon-ss-pack-")
        json.dump({"pantheon_pack": 1, "name": "acme",
                   "standards": "prefer stdlib; tests before merge",
                   "lessons": [{"text": "the staging db resets nightly, never rely on its rows"}]},
                  open(os.path.join(d, "pantheon.pack.json"), "w"))
        conn = _store.connect(os.path.join(d, "t.db"))
        line1 = import_pack(d, conn)
        assert "acme" in line1 and "stdlib" in line1
        assert conn.execute("SELECT COUNT(*) FROM lessons WHERE source='pack'").fetchone()[0] == 1
        import_pack(d, conn)  # same hash → no duplicate import
        assert conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 1
        conn.close()
        assert import_pack("/nonexistent") == ""
    # update check: version compare + disabled + no-plugin-root all safe
    assert _newer("0.8.0", "0.7.0") and not _newer("0.5.0", "0.5.0") and not _newer("x", "0.5.0")
    assert check_update({"updateCheck": False}) == ""
    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
    assert check_update({"updateCheck": True}) == ""  # no root → silent, no network
    print("selftest ok — directives + shim + update-check guards")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)
