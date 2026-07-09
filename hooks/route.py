#!/usr/bin/env python3
"""pantheon prompt router (UserPromptSubmit hook).

Reads the user's prompt, detects which discipline it calls for, and injects
a routing hint so the agent invokes the right pantheon skill automatically.
The user can always invoke skills explicitly — explicit beats automatic.

Design constraints:
- NEVER break the session: any failure exits 0 silently.
- Silent unless the signal is strong. A noisy router is worse than none.
- At most ONE route per prompt (the highest-priority match).
- stdlib only. Self-check: python3 route.py --selftest
"""
import sys, os, json, re, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import config as _config
except Exception:
    _config = None

# Priority-ordered routing table: first match wins.
# Patterns require word boundaries; all matching is case-insensitive.
ROUTES = [
    ("hydra", r"\b(nasty bug|hard bug|difficult bug|bug (keeps|is back|returns|again)|"
              r"regression|flaky|keeps? (failing|breaking|happening)|"
              r"can'?t (figure|work) out (why|what)|no idea why|"
              r"(fix|debug) (this|the) (bug|crash|error|issue))\b"),
    ("argus", r"\b(entire (codebase|repo)|whole (codebase|repo)|all (the )?files|"
              r"every (file|module|call ?site)|migrate everything|huge (task|input|file|dataset)|"
              r"too big|massive (refactor|migration|audit)|rlmit)\b"),
    ("athena", r"\b(design (the|this|a|my)? ?(ui|ux|page|component|screen|interface|layout)|"
               r"(build|make|create) (a |the |this )?(ui|component|page|landing|dashboard|screen|form|modal)|"
               r"looks? (bad|generic|off|ugly|boring|like ai)|make it (look )?(good|better|beautiful|pretty|nicer)|"
               r"(improve|polish) the (ui|ux|design|look|styling)|frontend design|the design)\b"),
    ("daedalus", r"\b(build (this|it|me)? ?(right|properly)|do (this|it) properly|"
                 r"once and for all|production[- ]quality|"
                 r"(implement|build|create|add) (the |a |an )?[a-z0-9_-]+ (feature|system|module|integration)|"
                 r"new feature)\b"),
    ("themis", r"\b(review (this|my|the)|code review|audit (this|the|my)|"
               r"is this (correct|right|safe)|check my (code|diff|change)|"
               r"find (bugs|issues|problems) in)\b"),
    ("oracle", r"\b(how (do|to) (i|we|you) use|what'?s the api|which (library|sdk|package)|"
               r"latest (version|docs)|read the docs|documentation for|"
               r"is there a (library|package|sdk))\b"),
    ("charon", r"\b(commit (this|it|the)|open a pr|pull request|land (it|this)|"
               r"push (this|it|the)|finish the branch|ready to merge)\b"),
    ("prometheus", r"\b(tdd|test[- ]first|test[- ]driven|red[- ]green|"
                   r"write (the )?tests? (first|before))\b"),
    ("mnemosyne", r"\b(remember (this|that)|don'?t forget|from now on|"
                  r"always do|never do|my preference|learn from this)\b"),
    ("lethe", r"\b(simplest|minimal(ist)?|yagni|over[- ]?engineer(ed|ing)?|"
              r"too (complex|complicated|much)|keep it simple|do less|bloat(ed)?)\b"),
    ("arachne", r"\b(map (the|this|our)? ?(code ?base|repo|project|dependencies)|"
                r"build (the|a)? ?(graph|dependency map)|graphify|knowledge graph|"
                r"visuali[sz]e (the )?(code ?base|repo|dependencies)|dependency (map|graph))\b"),
    ("alexandria", r"\b(document (this|the|it)|write (it|this) (to the )?(wiki|docs)|"
                   r"(add|update) (a |the )?(wiki|adr|decision record)|knowledge base|"
                   r"what do we know about|is there a (doc|page) (on|about))\b"),
    ("ariadne", r"\b(how does\b.{0,40}\bwork|where (is|does|do)|"
                r"understand (the|this) (code(base)?|repo|project|flow)|"
                r"get up to speed|orient|walk me through)\b"),
]

PERSISTENCE = re.compile(
    r"\b(keep going until|don'?t stop|until (it'?s|its) done|must complete|"
    r"work until|no matter how long)\b", re.IGNORECASE)


def detect(prompt: str):
    """Return (skill, persistence) for a prompt. skill may be None."""
    if not prompt or "pantheon:" in prompt or prompt.lstrip().startswith("/"):
        return None, False  # explicit invocation or slash command — stay silent
    skill = None
    for name, pattern in ROUTES:
        if re.search(pattern, prompt, re.IGNORECASE):
            skill = name
            break
    return skill, bool(PERSISTENCE.search(prompt))


def remember(skill: str, cwd: str) -> None:
    """Record the last route for the HUD. Best-effort."""
    try:
        d = os.path.join(os.path.expanduser("~"), ".claude", "pantheon")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "last-route.json"), "w", encoding="utf-8") as f:
            json.dump({"skill": skill, "at": datetime.datetime.now().isoformat(),
                       "cwd": cwd}, f)
    except Exception:
        pass


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd", "")
    cfg = _config.load(cwd) if _config else {"routing": "on", "disciplines": {}}
    if cfg.get("routing", "on") == "off":
        return 0  # automaticness disabled by config (quiet mode)
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    skill, persistent = detect(prompt)
    if not skill:
        return 0  # silence is a feature
    if _config and not _config.enabled(cfg, skill):
        return 0  # this discipline is disabled in config
    remember(skill, cwd)
    if cfg.get("routing") == "suggest":
        # economy: a soft one-line nudge, not an instruction — saves tokens
        print(f"[PANTHEON: this reads like a '{skill}' task — /pantheon:{skill} if you want it.]")
        return 0
    lines = [
        f"[PANTHEON ROUTE: {skill}]",
        f"This prompt matches the '{skill}' discipline. Invoke the Skill tool with "
        f"skill=\"pantheon:{skill}\" BEFORE responding, and follow it. If the match is "
        f"clearly incidental (the trigger word appeared in passing), proceed normally "
        f"and ignore this hint. An explicit skill/command from the user always wins.",
    ]
    if persistent:
        lines.append(
            "The prompt also asks for run-until-done persistence: if a persistence "
            "loop is available (e.g. oh-my-claudecode ralph), wrap the work in it; "
            "otherwise keep iterating with verification until the goal demonstrably "
            "passes, and say so honestly if blocked.")
    print("\n".join(lines))
    return 0


def selftest() -> int:
    cases = {
        "this bug keeps coming back after every deploy": "hydra",
        "we need to migrate everything in the entire codebase": "argus",
        "build this right, once and for all": "daedalus",
        "review this diff before I merge": "themis",
        "how do I use the stripe sdk here": "oracle",
        "ok commit this and open a PR": "charon",
        "let's do it test-first please": "prometheus",
        "remember this: I hate one-letter variables": "mnemosyne",
        "this feels over-engineered, keep it simple": "lethe",
        "how does the auth flow work in this repo": "ariadne",
        "design the settings page, it looks generic": "athena",
        "build the dependency graph for this project": "arachne",
        "document this decision in the wiki": "alexandria",
    }
    for prompt, want in cases.items():
        got, _ = detect(prompt)
        assert got == want, f"{prompt!r}: want {want}, got {got}"
    # Silence cases: no strong signal, explicit invocation, slash command.
    assert detect("thanks, looks great")[0] is None
    assert detect("what's the weather like")[0] is None
    assert detect("use pantheon:hydra on this")[0] is None
    assert detect("/pantheon:daedalus build the parser")[0] is None
    # Persistence flag rides along with a route.
    s, p = detect("fix this bug and keep going until it's done")
    assert s == "hydra" and p
    print("selftest ok — 13 routes, 4 silences, persistence flag")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)  # a hook must never break the session
