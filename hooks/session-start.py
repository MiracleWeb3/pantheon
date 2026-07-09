#!/usr/bin/env python3
"""pantheon SessionStart hook — inject active config once per session.

Only speaks when the config is non-default. In the default "full" experience it
stays completely silent (zero token cost). When economy/quiet/custom is set, it
injects one short directive that conditions every pantheon skill for the whole
session — so the static SKILL.md announce blocks defer to the user's choice
without needing to be re-read or edited.

Fail-silent. Self-check: python3 session-start.py --selftest
"""
import sys, os, json, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import config as _config
except Exception:
    _config = None


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
    line = directive(cfg)
    if line:
        print(line)
    upd = check_update(cfg)
    if upd:
        print(upd)
    return 0


def selftest() -> int:
    assert directive({"routing": "on", "announce": True, "preset": "full", "disciplines": {}}) == ""
    econ = directive({"routing": "suggest", "announce": False, "preset": "economy", "disciplines": {}})
    assert "economy" in econ and "announce" in econ and "terse" in econ
    quiet = directive({"routing": "off", "announce": False, "preset": "quiet", "disciplines": {}})
    assert "OFF" in quiet
    dis = directive({"routing": "on", "announce": True, "preset": "custom", "disciplines": {"athena": False}})
    assert "athena" in dis
    # update check: version compare + disabled + no-plugin-root all safe
    assert _newer("0.6.0", "0.5.9") and not _newer("0.5.0", "0.5.0") and not _newer("x", "0.5.0")
    assert check_update({"updateCheck": False}) == ""
    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
    assert check_update({"updateCheck": True}) == ""  # no root → silent, no network
    print("selftest ok — directives + update-check guards")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)
