#!/usr/bin/env python3
"""pantheon config loader — shared by the hooks.

Resolves configuration from, in order of precedence:
  1. <project>/.pantheon/config.json   (project-local, wins)
  2. ~/.claude/pantheon/config.json     (user-global)
  3. built-in defaults (preset "full")

A `preset` expands to a set of flags; explicit flags override the preset.
Everything is best-effort: a missing or malformed file falls back to defaults,
never an error (a broken config must not break the session).

Presets:
  full     routing on,      announce on    (default — the whole experience)
  economy  routing suggest,  announce off   (save tokens: no announce blocks, softer routing)
  quiet    routing off,      announce off   (fully manual: invoke skills yourself)

Explicit keys (override the preset):
  "routing":   "on" | "suggest" | "off"
  "announce":  true | false
  "disciplines": { "athena": false, ... }   # per-skill opt-out

Self-check:  python3 config.py --selftest
"""
import os, json

PRESETS = {
    "full":    {"routing": "on",      "announce": True},
    "economy": {"routing": "suggest", "announce": False},
    "quiet":   {"routing": "off",     "announce": False},
}
DEFAULT = dict(PRESETS["full"], disciplines={}, updateCheck=True)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def load(cwd: str = "") -> dict:
    """Return the resolved config dict: routing, announce, disciplines."""
    raw = {}
    home = os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "config.json")
    raw.update(_read(home))
    if cwd:
        raw.update(_read(os.path.join(cwd, ".pantheon", "config.json")))  # project wins

    cfg = dict(DEFAULT)
    preset = raw.get("preset")
    if preset in PRESETS:
        cfg.update(PRESETS[preset])
        cfg["disciplines"] = {}
    # explicit keys override the preset
    if raw.get("routing") in ("on", "suggest", "off"):
        cfg["routing"] = raw["routing"]
    if isinstance(raw.get("announce"), bool):
        cfg["announce"] = raw["announce"]
    if isinstance(raw.get("disciplines"), dict):
        cfg["disciplines"] = {k: bool(v) for k, v in raw["disciplines"].items()}
    if isinstance(raw.get("updateCheck"), bool):
        cfg["updateCheck"] = raw["updateCheck"]
    cfg["preset"] = preset if preset in PRESETS else "custom" if raw else "full"
    return cfg


def enabled(cfg: dict, skill: str) -> bool:
    """A skill is enabled unless explicitly disabled in config."""
    return cfg.get("disciplines", {}).get(skill, True)


def selftest() -> int:
    d = load("/nonexistent")
    assert d["routing"] == "on" and d["announce"] is True and d["preset"] == "full"
    # preset expansion (simulate by monkey-reading is overkill; test the merge logic)
    assert PRESETS["economy"] == {"routing": "suggest", "announce": False}
    assert enabled({"disciplines": {"athena": False}}, "athena") is False
    assert enabled({"disciplines": {"athena": False}}, "hydra") is True
    assert enabled({}, "hydra") is True
    print("selftest ok — presets:", ", ".join(PRESETS))
    return 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print(json.dumps(load(os.getcwd()), indent=2))
