#!/usr/bin/env python3
"""pantheon prompt hook (UserPromptSubmit) — route, clarify, guard.

Three jobs on every user prompt:
  1. ROUTE — detect which discipline the prompt calls for and inject a hint so
     the agent invokes the right pantheon skill automatically. Explicit always
     beats automatic. Custom routes from config win over built-ins. ADAPTIVE:
     every fire is logged with its outcome; a route you keep ignoring demotes
     itself to a soft suggestion (decayed stats — old evidence fades).
  2. CLARIFY — a broad, unanchored build request (no files/functions/specs
     named) triggers 2–3 sharp questions BEFORE any work. Kills wrong-thing-
     built waste at the cheapest possible moment.
  3. CONTEXT GUARD — when the context window passes the configured fill %%,
     inject a checkpoint directive so /compact or /clear loses nothing.

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
    import transcript as _tr
except Exception:
    _config = _store = _paths = _tr = None

# Priority-ordered routing table: first match wins.
# Patterns require word boundaries; all matching is case-insensitive.
ROUTES = [
    ("clio", r"\b(pantheon (dashboard|stats|status|report)|"
                  r"show (me )?(the )?dashboard|"
                  r"what (did|have) (you|we|pantheon) (do|done) (today|this week|lately))\b"),
    ("asclepius", r"\b(pantheon (doctor|is broken|isn'?t working|not working|acting up)|"
               r"fix pantheon|(diagnose|repair) (the )?plugin|"
               r"plugin (is )?(broken|not working))\b"),
    ("hephaestus", r"\b((create|make|forge|scaffold) (a |my )?(new |custom )?(skill|discipline)|"
              r"new (custom )?discipline|custom discipline|"
              r"(share|import) (a |my |this )?(skill|discipline))\b"),
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
               r"(improve|polish) the (ui|ux|design|look|styling)|frontend design)\b"),
    ("daedalus", r"\b(build (this|it|me)? ?(right|properly)|do (this|it) properly|"
                 r"once and for all|production[- ]quality|"
                 r"(implement|build|create|add) (the |a |an )?[a-z0-9_-]+ (feature|system|module|integration)|"
                 r"new feature)\b"),
    ("themis", r"\b(review (this|my|the)|code review|audit (this|the|my)|"
               r"is this (correct|right|safe)|check my (code|diff|change)|"
               r"find (bugs|issues|problems) in)\b"),
    ("sibyl", r"\b(how (do|to) (i|we|you) use|what'?s the api|which (library|sdk|package)|"
               r"latest (version|docs)|read the docs|documentation for|"
               r"is there a (library|package|sdk))\b"),
    ("charon", r"\b(commit (this|it|the)|open a pr|pull request|land (it|this)|"
               r"push (this|it|the)|finish the branch|ready to merge)\b"),
    ("prometheus", r"\b(tdd|test[- ]first|test[- ]driven|red[- ]green|"
                   r"write (the )?tests? (first|before))\b"),
    ("lethe", r"\b(simplest|minimal(ist)?|yagni|over[- ]?engineer(ed|ing)?|"
              r"too (complex|complicated)|keep it simple|do less|bloat(ed)?)\b"),
    ("arachne", r"\b(map (the|this|our)? ?(code ?base|repo|project|dependencies)|"
                r"build (the|a)? ?(graph|dependency map)|graphify|knowledge graph|"
                r"visuali[sz]e (the )?(code ?base|repo|dependencies)|dependency (map|graph))\b"),
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
        if len(pattern) > 200:
            continue  # ponytail: length cap + truncated haystack beats a regex
        try:      # complexity analyzer; kills catastrophic-backtracking stalls
            if re.search(pattern, prompt[:2000], re.IGNORECASE):
                return skill, persist, "custom:" + skill
        except re.error:
            continue
    for name, pattern in ROUTES:
        if re.search(pattern, prompt, re.IGNORECASE):
            return name, persist, name
    return None, persist, None


def remember(skill: str) -> None:
    """Record the last route — display data for the HUD/dashboard only
    (outcome resolution reads the store, not this file)."""
    try:
        d = os.path.join(os.path.expanduser("~"), ".claude", "pantheon")
        _paths.write_json_atomic(
            os.path.join(d, "last-route.json"),
            {"skill": skill, "at": datetime.datetime.now().isoformat()})
    except Exception:
        pass


def route_lines(prompt, cfg, cwd, session):
    """The routing hint: (list of context lines, routed skill or None)."""
    if cfg.get("routing", "on") == "off":
        return [], None
    skill, persistent, cluster = detect(prompt, cfg.get("custom_routes") or {})
    if not skill:
        return [], None
    if _config and not _config.enabled(cfg, skill):
        return [], None
    demoted = False
    try:
        if _store:
            conn = _store.connect()
            st = _store.route_stats(conn, only=(cluster, skill)).get((cluster, skill))
            # adaptive routing: ≥5 resolved fires and <30% accepted → this
            # route annoys more than it helps; soften it to a suggestion.
            if st and st["resolved"] >= 5 and st["accepts"] / st["resolved"] < 0.30:
                demoted = True
            _store.log_route(conn, cluster, skill, session,
                             _paths.project_name(cwd) if _paths else "")
            conn.close()
    except Exception:
        pass
    remember(skill)
    ns = f"pantheon:{skill}" if not cluster.startswith("custom:") else skill
    if cfg.get("routing") == "suggest" or demoted:
        # economy / demoted: a soft one-line nudge, not an instruction
        tail = " (auto-demoted: this route was mostly ignored lately)" if demoted else ""
        return [f"[PANTHEON: this reads like a '{skill}' task — /{ns} if you want it.{tail}]"], skill
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
    return lines, skill


# ── intent clarifier ─────────────────────────────────────────────────────────
BIG_RE = re.compile(
    r"\b(build|create|implement|redesign|rewrite|refactor|make|add|develop)\b"
    r".{0,80}?\b(system|app|application|feature|platform|dashboard|website|site|"
    r"service|pipeline|integration|tool|bot|module|api|game|store|marketplace)\b",
    re.IGNORECASE | re.DOTALL)
ANCHOR_RE = re.compile(
    r"[\w-]+\.[a-z]{1,4}\b|`[^`]+`|\b(def|class|function|func)\s+\w+|"
    r"(?<![\w.])/[\w./-]{4,}|#\d+\b")


def clarify_lines(prompt, cfg, routed_skill):
    """Vague + large + unrouted → demand 2–3 sharp questions before work."""
    if not cfg.get("clarify") or routed_skill:
        return []  # a routed discipline brings its own scoping steps
    words = len((prompt or "").split())
    if words < 6 or words > 90:  # short = conversational; long = already a spec
        return []
    if not BIG_RE.search(prompt) or ANCHOR_RE.search(prompt):
        return []
    return ["[PANTHEON CLARIFY] This request is broad and unanchored — no files, "
            "functions, or concrete specs are named. Before building anything, ask "
            "the user 2–3 sharp questions (scope boundary, success criteria, "
            "constraints/stack — use AskUserQuestion if available), then restate the "
            "plan in one line and proceed. Skip the questions only if the "
            "conversation already answered them."]


# ── context guard ────────────────────────────────────────────────────────────
def _guard_state_path():
    return os.path.join(os.path.expanduser("~"), ".claude", "pantheon",
                        "context-guard.json")


def context_lines(transcript_path, session, cfg):
    """Past the fill threshold → one checkpoint directive (once per level)."""
    thr = int(cfg.get("context_guard", 0) or 0)
    if not thr or not _tr or not transcript_path:
        return []
    pct = _tr.context_pct(transcript_path)
    if pct < thr:
        return []
    level = "high" if pct >= 93 else "base"
    try:
        st = json.load(open(_guard_state_path(), encoding="utf-8"))
    except Exception:
        st = {}
    fired = st.get(session, [])
    if level in fired:
        return []
    try:
        st[session] = fired + [level]
        if len(st) > 40:  # keep the state file small across many sessions
            st = {session: fired + [level]}
        _paths.write_json_atomic(_guard_state_path(), st)
    except Exception:
        pass
    urgency = ("very nearly full — checkpoint NOW, before answering"
               if level == "high" else "filling up")
    return [f"[PANTHEON CONTEXT] The context window is ~{pct}% {urgency}. "
            "Write a checkpoint so nothing is lost to /compact or /clear: the live "
            "plan, open threads, and key decisions — to a file in the repo "
            "(a WIP doc, the plan file, or your notes). Then continue the task and suggest /compact at the next "
            "natural pause."]


# ── cost guardrails ──────────────────────────────────────────────────────────
_BUDGET_STATE = os.path.join(os.path.expanduser("~"), ".claude", "pantheon",
                             "budget-state.json")


def _ledger_sums():
    """(last-24h, last-7d) USD from the HUD spend ledger."""
    ev = os.path.join(os.path.expanduser("~"), ".claude", "pantheon",
                      "usage-events.jsonl")
    s24 = s7 = 0.0
    now = time.time()
    try:
        for ln in open(ev, encoding="utf-8"):
            try:
                e = json.loads(ln)
                t = datetime.datetime.fromisoformat(e["t"]).timestamp()
                d = float(e["d"])
                if now - t <= 7 * 86400:
                    s7 += d
                    if now - t <= 86400:
                        s24 += d
            except Exception:
                continue  # one bad line must not abort the whole scan
    except Exception:
        pass
    return s24, s7


def _session_cost(session):
    try:
        st = json.load(open(os.path.join(os.path.expanduser("~"), ".claude",
                                         "pantheon", "usage-state.json"),
                            encoding="utf-8"))
        v = st.get(session, 0.0)
        return float(v.get("c", 0.0) if isinstance(v, dict) else v)
    except Exception:
        return 0.0


def _fired_before(session, key):
    """True if this budget level already fired this session; records it if not."""
    try:
        st = json.load(open(_BUDGET_STATE, encoding="utf-8"))
    except Exception:
        st = {}
    fired = st.get(session, [])
    if key in fired:
        return True
    try:
        st[session] = fired + [key]
        if len(st) > 40:
            st = {session: fired + [key]}
        _paths.write_json_atomic(_BUDGET_STATE, st)
    except Exception:
        pass
    return False


def budget_output(prompt, cfg, session):
    """Cost guardrails: (context lines, block dict or None). Caps come from
    config; spend comes from the HUD's self-maintained ledger. mode:
    warn = tell the user once · ask = require an explicit go-ahead ·
    block = refuse further prompts (saying 'budget' passes through)."""
    b = cfg.get("budget") or {}
    caps = {s: float(b[s]) for s in ("session", "daily", "weekly")
            if isinstance(b.get(s), (int, float)) and b[s] > 0}
    if not caps:
        return [], None
    s24, s7 = _ledger_sums()
    spend = {"session": _session_cost(session), "daily": s24, "weekly": s7}
    mode = b.get("mode", "warn")
    for scope in ("session", "daily", "weekly"):
        cap = caps.get(scope)
        if cap is None:
            continue
        sp = spend[scope]
        if sp >= cap:
            if mode == "block" and "budget" not in (prompt or "").lower():
                return [], {"decision": "block", "reason":
                            f"pantheon budget: {scope} spend ${sp:.2f} has hit the "
                            f"${cap:.2f} cap. Raise or remove budget.{scope} in "
                            f"~/.claude/pantheon/config.json, set budget.mode to "
                            f"\"warn\", or include the word 'budget' in your message "
                            f"— those pass through so you can sort it out."}
            if _fired_before(session, f"100:{scope}"):
                return [f"[PANTHEON BUDGET] still over the {scope} cap "
                        f"(${sp:.2f}/${cap:.2f}) — stay token-frugal."], None
            if mode == "ask":
                return [f"[PANTHEON BUDGET] The {scope} budget is exhausted "
                        f"(${sp:.2f} of ${cap:.2f}). Before any token-heavy work, "
                        f"tell the user and ASK whether to continue or wind down; "
                        f"honor their answer for the rest of the session."], None
            return [f"[PANTHEON BUDGET] The {scope} budget cap is exceeded "
                    f"(${sp:.2f} of ${cap:.2f}). Tell the user in one short line at "
                    f"the start of your reply and keep responses token-frugal."], None
        if sp >= 0.8 * cap and not _fired_before(session, f"80:{scope}"):
            return [f"[PANTHEON BUDGET] {scope} spend ${sp:.2f} is at "
                    f"{int(sp / cap * 100)}% of the ${cap:.2f} cap — mention it "
                    f"briefly and prefer token-frugal approaches."], None
    return [], None


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd", "")
    session = payload.get("session_id", "")
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    cfg = _config.load(cwd) if _config else dict(routing="on", disciplines={})

    out, routed = [], None
    try:
        blines, block = budget_output(prompt, cfg, session)
        if block:
            print(json.dumps(block))
            return 0
        out += blines
    except Exception:
        pass
    try:
        lines, routed = route_lines(prompt, cfg, cwd, session)
        out += lines
    except Exception:
        pass
    try:
        out += clarify_lines(prompt, cfg, routed)
    except Exception:
        pass
    try:
        out += context_lines(payload.get("transcript_path", ""), session, cfg)
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
        "how do I use the stripe sdk here": "sibyl",
        "ok commit this and open a PR": "charon",
        "let's do it test-first please": "prometheus",
        "this feels over-engineered, keep it simple": "lethe",
        "how does the auth flow work in this repo": "ariadne",
        "design the settings page, it looks generic": "athena",
        "build the dependency graph for this project": "arachne",
                "show me the pantheon dashboard": "clio",
        "pantheon isn't working, routing went silent": "asclepius",
        "let's forge a new skill for our deploy ritual": "hephaestus",
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
    # tightened routes: former false fires stay silent, true fires still hit
    assert detect("the design doc says to use postgres here")[0] is None
    assert detect("this api call costs too much money")[0] is None
    assert detect("this feels too complicated somehow")[0] == "lethe"
    # Custom routes win over built-ins; bad regexes are skipped safely.
    got, _, cluster = detect("deploy this to fly for me",
                             {"deploy .* fly": "my-deploy", "([bad": "x"})
    assert got == "my-deploy" and cluster == "custom:my-deploy"
    # oversized custom pattern is skipped, a sane sibling still matches
    got, _, _ = detect("deploy the thing please", {"x" * 300: "nope", "deploy": "ok-skill"})
    assert got == "ok-skill"
    # Persistence flag rides along with a route.
    s, p, _ = detect("fix this bug and keep going until it's done")
    assert s == "hydra" and p
    # memory belongs to claude-memory-light — this hook must not grow recall back
    assert "recall_lines" not in globals()
    # Clarifier: vague+large fires; anchored / short / routed / disabled don't.
    on = {"clarify": True}
    assert clarify_lines("build me a booking system for my gym members", on, None)
    assert clarify_lines("build the parser system in scraper.py please", on, None) == []
    assert clarify_lines("make an app", on, None) == []
    assert clarify_lines("build me a booking system for my gym members", on, "daedalus") == []
    assert clarify_lines("build me a booking system for my gym members",
                         {"clarify": False}, None) == []
    # Context guard: threshold 0 or no transcript → silent.
    assert context_lines("", "s", {"context_guard": 85}) == []
    assert context_lines("/nonexistent", "s", {"context_guard": 0}) == []
    # Budget: no caps → silent; over-cap block honors the 'budget' passthrough;
    # warn fires full text once then a short reminder; 80% fires once.
    global _ledger_sums, _session_cost, _BUDGET_STATE
    import tempfile
    assert budget_output("x", {"budget": {}}, "s") == ([], None)
    _BUDGET_STATE = os.path.join(tempfile.mkdtemp(prefix="pantheon-bs-"), "b.json")
    keep = (_ledger_sums, _session_cost)
    _ledger_sums = lambda: (0.0, 30.0)
    _session_cost = lambda s: 0.0
    cfgb = {"budget": {"weekly": 25.0, "mode": "block"}}
    lines, block = budget_output("do big work", cfgb, "s1")
    assert block and block["decision"] == "block" and "weekly" in block["reason"]
    lines, block = budget_output("raise my budget please", cfgb, "s1")
    assert block is None and lines and "exceeded" in lines[0]
    lines, _ = budget_output("more budget talk", cfgb, "s1")
    assert "still over" in lines[0]
    _ledger_sums = lambda: (0.0, 21.0)  # 84% of 25
    cfgw = {"budget": {"weekly": 25.0, "mode": "warn"}}
    lines, _ = budget_output("hello there friend", cfgw, "s2")
    assert lines and "84%" in lines[0]
    assert budget_output("hello again friend", cfgw, "s2") == ([], None)
    _ledger_sums, _session_cost = keep
    print("selftest ok — 16 routes, 4 silences, custom routes, persistence, "
          "clarifier, context guard, budget modes")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)  # a hook must never break the session
