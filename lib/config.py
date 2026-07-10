#!/usr/bin/env python3
"""pantheon config loader — shared by every hook and script.

Resolves configuration from, in order of precedence:
  1. <project>/.pantheon/config.json   (project-local, wins)
  2. pantheon.pack.json                 (team pack, found walking up from cwd)
  3. ~/.claude/pantheon/config.json     (user-global)
  4. built-in defaults (preset "full")

A team pack is a committed file that carries preset/overrides/disciplines,
team standards, and shared lessons — set "packs": false to opt out of it.

A `preset` expands to a set of flags; explicit flags override the preset.
Everything is best-effort: a missing or malformed file falls back to defaults,
never an error (a broken config must not break the session).

Presets:
  full     the whole experience: routing on, announce, recall 3, gate blocks,
           clarifier + context guard on, receipts on
  economy  save tokens: routing suggests, no announce, recall 1, gate warns
  quiet    fully manual: no routing, no recall, no gate, no receipts

Explicit keys (override the preset):
  "routing":        "on" | "suggest" | "off"
  "announce":       true | false
  "recall":         0..3            # max past lessons injected per prompt
  "gate":           "block" | "warn" | "off"
  "clarify":        true | false    # auto intent-clarifier on vague big asks
  "context_guard":  0..99           # context %% that triggers a checkpoint nudge (0 = off)
  "receipts":       true | false
  "budget":         {"session": 5.0, "daily": null, "weekly": 25.0, "mode": "warn"|"ask"|"block"}
  "disciplines":    {"athena": false, ...}    # per-skill opt-out
  "custom_routes":  {"deploy to fly": "my-deploy-skill", ...}   # regex -> skill
  "updateCheck":    true | false

Self-check:  python3 config.py --selftest
"""
import os, json

PRESETS = {
    "full":    {"routing": "on",      "announce": True,  "recall": 3, "gate": "block",
                "clarify": True,  "context_guard": 85, "receipts": True},
    "economy": {"routing": "suggest", "announce": False, "recall": 1, "gate": "warn",
                "clarify": True,  "context_guard": 90, "receipts": True},
    "quiet":   {"routing": "off",     "announce": False, "recall": 0, "gate": "off",
                "clarify": False, "context_guard": 0,  "receipts": False},
}
DEFAULT = dict(PRESETS["full"], disciplines={}, custom_routes={}, updateCheck=True,
               budget={"session": None, "daily": None, "weekly": None, "mode": "warn"})


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _merge_layer(raw: dict, layer: dict) -> None:
    """Overlay one config source; dict-valued keys union instead of replace."""
    for k, v in layer.items():
        if k in ("disciplines", "custom_routes", "budget") and isinstance(v, dict):
            base = raw.get(k)
            raw[k] = dict(base if isinstance(base, dict) else {}, **v)
        else:
            raw[k] = v


def find_pack(cwd: str):
    """Walk up from cwd for a pantheon.pack.json. Returns (path, dict) or ('', {})."""
    d = cwd or ""
    for _ in range(12):
        if not d or not os.path.isdir(d):
            break
        p = os.path.join(d, "pantheon.pack.json")
        if os.path.isfile(p):
            pk = _read(p)
            return (p, pk) if pk.get("pantheon_pack") else ("", {})
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return "", {}


def load(cwd: str = "") -> dict:
    """Return the fully-resolved config dict."""
    raw = {}
    home = os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "config.json")
    g = _read(home)
    proj = _read(os.path.join(cwd, ".pantheon", "config.json")) if cwd else {}
    _merge_layer(raw, g)
    if cwd and proj.get("packs", g.get("packs", True)) is not False:
        _, pk = find_pack(cwd)
        if pk:
            layer = {}
            if pk.get("preset") in PRESETS:
                layer["preset"] = pk["preset"]
            if isinstance(pk.get("overrides"), dict):
                layer.update(pk["overrides"])
            if isinstance(pk.get("disciplines"), dict):
                layer["disciplines"] = pk["disciplines"]
            _merge_layer(raw, layer)  # pack sits between global and project
    _merge_layer(raw, proj)  # project wins

    cfg = json.loads(json.dumps(DEFAULT))  # deep copy (budget is nested)
    preset = raw.get("preset")
    if preset in PRESETS:
        cfg.update(PRESETS[preset])
    # explicit keys override the preset
    if raw.get("routing") in ("on", "suggest", "off"):
        cfg["routing"] = raw["routing"]
    for key in ("announce", "clarify", "receipts", "updateCheck"):
        if isinstance(raw.get(key), bool):
            cfg[key] = raw[key]
    if isinstance(raw.get("recall"), bool):
        cfg["recall"] = 3 if raw["recall"] else 0
    elif isinstance(raw.get("recall"), int):
        cfg["recall"] = max(0, min(3, raw["recall"]))
    if raw.get("gate") in ("block", "warn", "off"):
        cfg["gate"] = raw["gate"]
    if isinstance(raw.get("context_guard"), (int, float)):
        cfg["context_guard"] = max(0, min(99, int(raw["context_guard"])))
    if isinstance(raw.get("disciplines"), dict):
        cfg["disciplines"] = {k: bool(v) for k, v in raw["disciplines"].items()}
    if isinstance(raw.get("custom_routes"), dict):
        cfg["custom_routes"] = {str(k): str(v) for k, v in raw["custom_routes"].items()
                                if isinstance(k, str) and isinstance(v, str)}
    if isinstance(raw.get("budget"), dict):
        b = cfg["budget"]
        for scope in ("session", "daily", "weekly"):
            v = raw["budget"].get(scope, b.get(scope))
            b[scope] = float(v) if isinstance(v, (int, float)) and v > 0 else None
        if raw["budget"].get("mode") in ("warn", "ask", "block"):
            b["mode"] = raw["budget"]["mode"]
    cfg["preset"] = preset if preset in PRESETS else "custom" if raw else "full"
    cfg["packs"] = raw.get("packs", True) is not False
    return cfg


def enabled(cfg: dict, skill: str) -> bool:
    """A skill is enabled unless explicitly disabled in config."""
    return cfg.get("disciplines", {}).get(skill, True)


KNOWN_KEYS = {"_comment", "preset", "routing", "announce", "recall", "gate", "clarify",
              "context_guard", "receipts", "budget", "disciplines", "custom_routes",
              "updateCheck", "packs"}


def validate(raw: dict):
    """Return a list of warnings for a raw config dict (used by doctor)."""
    warns = [f"unknown key: {k!r}" for k in raw if k not in KNOWN_KEYS]
    if "preset" in raw and raw["preset"] not in PRESETS:
        warns.append(f"unknown preset: {raw['preset']!r} (full/economy/quiet)")
    if raw.get("gate") not in (None, "block", "warn", "off"):
        warns.append(f"bad gate value: {raw['gate']!r}")
    return warns


def selftest() -> int:
    d = load("/nonexistent")
    assert d["routing"] == "on" and d["announce"] is True and d["preset"] == "full"
    assert d["recall"] == 3 and d["gate"] == "block" and d["context_guard"] == 85
    assert d["budget"]["mode"] == "warn" and d["budget"]["weekly"] is None
    assert PRESETS["quiet"]["gate"] == "off" and PRESETS["economy"]["gate"] == "warn"
    assert enabled({"disciplines": {"athena": False}}, "athena") is False
    assert enabled({}, "hydra") is True
    # merge semantics: dict keys union across layers
    raw = {}
    _merge_layer(raw, {"disciplines": {"a": False}, "budget": {"weekly": 20}})
    _merge_layer(raw, {"disciplines": {"b": False}, "budget": {"mode": "block"}})
    assert raw["disciplines"] == {"a": False, "b": False}
    assert raw["budget"] == {"weekly": 20, "mode": "block"}
    assert validate({"nonsense": 1}) and not validate({"preset": "full"})
    # team pack: found walking up, sits between global and project, opt-out works
    import tempfile
    top = tempfile.mkdtemp(prefix="pantheon-pack-")
    sub = os.path.join(top, "a", "b")
    os.makedirs(sub)
    json.dump({"pantheon_pack": 1, "preset": "economy",
               "overrides": {"gate": "warn"}, "disciplines": {"athena": False}},
              open(os.path.join(top, "pantheon.pack.json"), "w"))
    path, pk = find_pack(sub)
    assert path.endswith("pantheon.pack.json") and pk["preset"] == "economy"
    cfg = load(sub)
    assert cfg["preset"] == "economy" and cfg["gate"] == "warn"
    assert cfg["disciplines"] == {"athena": False}
    os.makedirs(os.path.join(sub, ".pantheon"))
    json.dump({"gate": "block", "packs": True},
              open(os.path.join(sub, ".pantheon", "config.json"), "w"))
    assert load(sub)["gate"] == "block"  # project overrides the pack
    json.dump({"packs": False}, open(os.path.join(sub, ".pantheon", "config.json"), "w"))
    out = load(sub)
    # pack fully ignored: gate back to the default, economy preset gone
    # (preset reads "custom" because a config file exists — that's correct)
    assert out["gate"] == "block" and out["routing"] == "on" and out["preset"] == "custom"
    assert find_pack("/nonexistent") == ("", {})
    print("selftest ok — presets:", ", ".join(PRESETS), "+ team packs")
    return 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print(json.dumps(load(os.getcwd()), indent=2))
