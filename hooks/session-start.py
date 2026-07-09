#!/usr/bin/env python3
"""pantheon SessionStart hook — inject active config once per session.

Only speaks when the config is non-default. In the default "full" experience it
stays completely silent (zero token cost). When economy/quiet/custom is set, it
injects one short directive that conditions every pantheon skill for the whole
session — so the static SKILL.md announce blocks defer to the user's choice
without needing to be re-read or edited.

Fail-silent. Self-check: python3 session-start.py --selftest
"""
import sys, os, json

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


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd") or os.getcwd()
    cfg = _config.load(cwd) if _config else {"routing": "on", "announce": True, "preset": "full"}
    line = directive(cfg)
    if line:
        print(line)
    return 0


def selftest() -> int:
    assert directive({"routing": "on", "announce": True, "preset": "full", "disciplines": {}}) == ""
    econ = directive({"routing": "suggest", "announce": False, "preset": "economy", "disciplines": {}})
    assert "economy" in econ and "announce" in econ and "terse" in econ
    quiet = directive({"routing": "off", "announce": False, "preset": "quiet", "disciplines": {}})
    assert "OFF" in quiet
    dis = directive({"routing": "on", "announce": True, "preset": "custom", "disciplines": {"athena": False}})
    assert "athena" in dis
    print("selftest ok — silent on full, speaks on economy/quiet/custom")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)
