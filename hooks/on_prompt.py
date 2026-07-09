#!/usr/bin/env python3
"""pantheon prompt hook (UserPromptSubmit) — route + recall.

Two jobs on every user prompt:
  1. ROUTE — detect which discipline the prompt calls for and inject a hint so
     the agent invokes the right pantheon skill automatically. Explicit always
     beats automatic. Custom routes from config win over built-ins.
     Every fire is logged to the store so routing can adapt to what you accept.
  2. RECALL — retrieval-augmented memory: match the prompt against captured
     lessons and inject the top 1–3 relevant ones. Memory that surfaces itself.

Design constraints:
- NEVER break the session: any failure exits 0 silently.
- Silent unless the signal is strong. A noisy hook is worse than none.
- stdlib only. Self-check: python3 on_prompt.py --selftest
"""
import sys, os, json, re, time, datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "lib"))
try:
    import config as _config
    import store as _store
    import paths as _paths
except Exception:
    _config = _store = _paths = None

# Priority-ordered routing table: first match wins.
# Patterns require word boundaries; all matching is case-insensitive.
ROUTES = [
    ("dashboard", r"\b(pantheon (dashboard|stats|status|report)|"
                  r"show (me )?(the )?dashboard|"
                  r"what (did|have) (you|we|pantheon) (do|done) (today|this week|lately))\b"),
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


def detect(prompt: str, custom: dict = None):
    """Return (skill, persistence, cluster). skill may be None.
    cluster is the stats key: the route name, or 'custom:<skill>'."""
    if not prompt or "pantheon:" in prompt or prompt.lstrip().startswith("/"):
        return None, False, None  # explicit invocation or slash command — stay silent
    persist = bool(PERSISTENCE.search(prompt))
    for pattern, skill in (custom or {}).items():
        try:
            if re.search(pattern, prompt, re.IGNORECASE):
                return skill, persist, "custom:" + skill
        except re.error:
            continue
    for name, pattern in ROUTES:
        if re.search(pattern, prompt, re.IGNORECASE):
            return name, persist, name
    return None, persist, None


def remember(skill: str, cwd: str, rowid, session: str) -> None:
    """Record the last route for the HUD and for outcome resolution on Stop."""
    try:
        d = os.path.join(os.path.expanduser("~"), ".claude", "pantheon")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "last-route.json"), "w", encoding="utf-8") as f:
            json.dump({"skill": skill, "at": datetime.datetime.now().isoformat(),
                       "cwd": cwd, "rowid": rowid, "session": session,
                       "resolved": False}, f)
    except Exception:
        pass


def route_lines(prompt, cfg, cwd, session):
    """The routing hint (list of context lines), or []."""
    if cfg.get("routing", "on") == "off":
        return []
    skill, persistent, cluster = detect(prompt, cfg.get("custom_routes") or {})
    if not skill:
        return []
    if _config and not _config.enabled(cfg, skill):
        return []
    rowid = None
    try:
        if _store:
            conn = _store.connect()
            rowid = _store.log_route(conn, cluster, skill, session,
                                     _paths.project_name(cwd) if _paths else "")
            conn.close()
    except Exception:
        pass
    remember(skill, cwd, rowid, session)
    ns = f"pantheon:{skill}" if not cluster.startswith("custom:") else skill
    if cfg.get("routing") == "suggest":
        # economy: a soft one-line nudge, not an instruction — saves tokens
        return [f"[PANTHEON: this reads like a '{skill}' task — /{ns} if you want it.]"]
    lines = [
        f"[PANTHEON ROUTE: {skill}]",
        f"This prompt matches the '{skill}' discipline. Invoke the Skill tool with "
        f"skill=\"{ns}\" BEFORE responding, and follow it. If the match is "
        f"clearly incidental (the trigger word appeared in passing), proceed normally "
        f"and ignore this hint. An explicit skill/command from the user always wins.",
    ]
    if persistent:
        lines.append(
            "The prompt also asks for run-until-done persistence: if a persistence "
            "loop is available (e.g. oh-my-claudecode ralph), wrap the work in it; "
            "otherwise keep iterating with verification until the goal demonstrably "
            "passes, and say so honestly if blocked.")
    return lines


def recall_lines(prompt, cfg, cwd, conn=None):
    """Retrieval-augmented memory: relevant past lessons, or []."""
    n = int(cfg.get("recall", 0) or 0)
    if not _store or n <= 0 or len(prompt or "") < 20:
        return []
    own = conn is None
    if own:
        conn = _store.connect()
    try:
        hits = _store.recall(conn, prompt,
                             keys=_paths.project_name(cwd) if _paths else "", limit=n)
    finally:
        if own:
            conn.close()
    if not hits:
        return []
    lines = ["[PANTHEON RECALL] Lessons captured in past sessions that match this "
             "prompt — apply what fits, ignore what doesn't:"]
    now = time.time()
    for h in hits:
        age = int(max(0, now - h["ts"]) // 86400)
        when = "today" if age == 0 else f"{age}d ago"
        lines.append(f"  • {h['text'][:240]}  ({when})")
    return lines


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd", "")
    session = payload.get("session_id", "")
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    cfg = _config.load(cwd) if _config else dict(routing="on", recall=0, disciplines={})

    out = []
    for part in (route_lines, ):
        try:
            out += part(prompt, cfg, cwd, session)
        except Exception:
            pass
    try:
        out += recall_lines(prompt, cfg, cwd)
    except Exception:
        pass
    if out:
        print("\n".join(out))
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
        "show me the pantheon dashboard": "dashboard",
    }
    for prompt, want in cases.items():
        got, _, cluster = detect(prompt)
        assert got == want, f"{prompt!r}: want {want}, got {got}"
        assert cluster == want
    # Silence cases: no strong signal, explicit invocation, slash command.
    assert detect("thanks, looks great")[0] is None
    assert detect("what's the weather like")[0] is None
    assert detect("use pantheon:hydra on this")[0] is None
    assert detect("/pantheon:daedalus build the parser")[0] is None
    # Custom routes win over built-ins; bad regexes are skipped safely.
    got, _, cluster = detect("deploy this to fly for me",
                             {"deploy .* fly": "my-deploy", "([bad": "x"})
    assert got == "my-deploy" and cluster == "custom:my-deploy"
    # Persistence flag rides along with a route.
    s, p, _ = detect("fix this bug and keep going until it's done")
    assert s == "hydra" and p
    # Recall path: quiet config or a short prompt stays silent.
    assert recall_lines("hi", {"recall": 3}, "") == []
    assert recall_lines("a long enough prompt about things", {"recall": 0}, "") == []
    print("selftest ok — 14 routes, 4 silences, custom routes, persistence, recall gates")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)  # a hook must never break the session
