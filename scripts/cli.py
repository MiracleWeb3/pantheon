#!/usr/bin/env python3
"""pantheon CLI — receipts, lessons, recall, stats, dashboard.

Reached via the shim `~/.claude/pantheon/bin/pantheon` (rewritten every
SessionStart to point at the installed plugin), or directly:
    python3 <plugin>/scripts/cli.py <command> ...

Commands:
    receipt add --skill S --note "..."     file a receipt for a discipline
    receipt list [--days 7]
    lesson add "text" [--tags a,b] [--keys proj] [--weight 1.3]
    lesson list [--limit 20] / lesson search "query"
    lesson import-inbox                    pull ⚠️-flagged inbox lines into the store
    recall "some prompt"                   debug what auto-recall would surface
    stats                                  counts, top disciplines, spend
    dashboard [--plain]                    the TUI (scripts/dashboard.py)
    doctor [--fix]                         diagnose + repair the install
    forge new NAME [--route REGEX] ...     scaffold a custom discipline
    forge export NAME / forge import FILE  share disciplines as single files
    pack init / pack status                team pack: config+lessons in the repo
    export --target cursor|codex|generic   package disciplines for other agents
    version

stdlib only. Self-check: python3 cli.py --selftest
"""
import sys, os, re, json, time, argparse, datetime, subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lib"))
import store, paths
import config as cfgmod


def _session():
    return os.environ.get("CLAUDE_SESSION_ID", "")


def _age(ts):
    d = max(0, time.time() - ts)
    if d < 3600:
        return f"{int(d // 60)}m"
    if d < 86400:
        return f"{int(d // 3600)}h"
    return f"{int(d // 86400)}d"


def cmd_receipt(a):
    conn = store.connect()
    if a.action == "add":
        if not a.skill or not a.note:
            print("need --skill and --note")
            return 2
        rid = store.add_receipt(conn, a.skill, a.note, session=_session(),
                                tokens=a.tokens, project=paths.project_name(os.getcwd()))
        print(f"receipt #{rid} · {a.skill} — {a.note}")
    else:
        rows = store.recent_receipts(conn, limit=a.limit, days=a.days)
        if not rows:
            print("no receipts yet")
        for r in rows:
            tok = f" · {r['tokens']}tok" if r["tokens"] else ""
            proj = f" · {r['project']}" if r["project"] else ""
            print(f"{_age(r['ts']):>4} · {r['skill']:<10} {r['note']}{tok}{proj}")
    return 0


def cmd_lesson(a):
    conn = store.connect()
    if a.action == "add":
        lid = store.add_lesson(conn, a.text, tags=a.tags, weight=a.weight,
                               keys=a.keys or paths.project_name(os.getcwd()),
                               source="manual")
        print(f"lesson #{lid} saved" if lid else "skipped (duplicate or too short)")
        return 0
    if a.action == "import-inbox":
        n = 0
        for p in (os.path.join(os.getcwd(), ".pantheon", "learning-inbox.md"),
                  os.path.join(paths.state_dir(), "learning-inbox.md")):
            try:
                for ln in open(p, encoding="utf-8"):
                    if "likely-correction" in ln and ln.lstrip().startswith("-"):
                        text = ln.split("likely-correction", 1)[1].strip()
                        if store.add_lesson(conn, text, tags="correction,inbox",
                                            keys=paths.project_name(os.getcwd()),
                                            source="auto"):
                            n += 1
            except Exception:
                continue
        print(f"imported {n} flagged inbox line(s) as lessons "
              "(inbox files untouched — consolidate/delete them yourself)")
        return 0
    q = "SELECT * FROM lessons ORDER BY ts DESC LIMIT ?"
    args = [a.limit]
    if a.action == "search" and a.text:
        q = ("SELECT * FROM lessons WHERE text LIKE ? OR tags LIKE ? "
             "ORDER BY ts DESC LIMIT ?")
        like = f"%{a.text}%"
        args = [like, like, a.limit]
    rows = list(conn.execute(q, args))
    if not rows:
        print("no lessons yet — `pantheon lesson add \"...\"` or let capture feed them")
    for r in rows:
        uses = f" ·{r['uses']}×" if r["uses"] else ""
        print(f"#{r['id']:<4}{_age(r['ts']):>4} [{r['source']}{uses}] {r['text'][:110]}")
    return 0


def cmd_recall(a):
    conn = store.connect()
    hits = store.recall(conn, a.text, keys=paths.project_name(os.getcwd()), limit=3)
    if not hits:
        print("nothing clears the relevance bar for that prompt")
    for h in hits:
        print(f"• ({_age(h['ts'])}, {h['source']}) {h['text'][:160]}")
    return 0


def _spend():
    """(today, last-7d) USD from the HUD's ledger; (0, 0) when absent."""
    day = time.time() - 86400
    week = time.time() - 7 * 86400
    s1 = s7 = 0.0
    try:
        for ln in open(os.path.join(paths.state_dir(), "usage-events.jsonl"),
                       encoding="utf-8"):
            try:
                e = json.loads(ln)
                t = datetime.datetime.fromisoformat(e["t"]).timestamp()
                d = float(e["d"])
                if t >= week:
                    s7 += d
                    if t >= day:
                        s1 += d
            except Exception:
                continue  # one bad line must not abort the whole scan
    except Exception:
        pass
    return s1, s7


def cmd_stats(a):
    conn = store.connect()
    c = store.counts(conn)
    print(f"store: {c['lessons']} lessons · {c['receipts']} receipts · "
          f"{c['routes']} routes · {c['metrics']} metrics")
    rows = list(conn.execute(
        "SELECT skill, COUNT(*) n FROM receipts WHERE ts>? GROUP BY skill "
        "ORDER BY n DESC LIMIT 6", (time.time() - 7 * 86400,)))
    if rows:
        print("7d disciplines: " + " · ".join(f"{r['skill']}×{r['n']}" for r in rows))
    s1, s7 = _spend()
    if s7:
        print(f"spend: ${s1:.2f} today · ${s7:.2f} last 7d")
    cfg = cfgmod.load(os.getcwd())
    print(f"config: preset={cfg['preset']} routing={cfg['routing']} gate={cfg['gate']} "
          f"recall={cfg['recall']} receipts={cfg['receipts']}")
    return 0


def cmd_dashboard(a):
    args = [sys.executable, os.path.join(_HERE, "dashboard.py")]
    if a.plain:
        args.append("--plain")
    return subprocess.call(args)


def cmd_doctor(a):
    args = [sys.executable, os.path.join(_HERE, "doctor.py")]
    if a.fix:
        args.append("--fix")
    return subprocess.call(args)


# ── forge: author + share custom disciplines ─────────────────────────────────
FORGE_TEMPLATE = """---
name: {name}
description: "{desc} Use when: {when}."
---

# {name} — {epithet}

<Why this discipline exists: the failure mode it prevents, in one paragraph.>

## Announce yourself — first (skipped in economy/quiet mode)

> 🏛 **{name}** — {epithet}. **Task:** <the user's goal, one line>. **Plan:** <your 2–4 concrete steps for THIS task>.

## The method

1. <step — what to do first and why>
2. <step>
3. <verify — how do you PROVE it worked, not just believe it?>

## Receipt — file your footprint (skipped in quiet mode)

`~/.claude/pantheon/bin/pantheon receipt add --skill {name} --note "<outcome, one line>"` — skip silently if the command is missing.

<!-- forged with `pantheon forge` -->
"""


def _skill_dirs(name):
    """Search order for an existing skill by name."""
    return [os.path.join(os.path.expanduser("~"), ".claude", "skills", name),
            os.path.join(os.getcwd(), ".claude", "skills", name),
            os.path.join(_ROOT, "skills", name)]


def cmd_forge(a):
    if a.action == "new":
        name = re.sub(r"[^a-z0-9-]", "-", a.name_or_file.lower()).strip("-")
        if not name:
            print("forge: give the discipline a name ([a-z0-9-])")
            return 2
        base = (os.path.join(os.getcwd(), ".claude", "skills") if a.project
                else os.path.join(os.path.expanduser("~"), ".claude", "skills"))
        dest = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(dest) and not a.force:
            print(f"forge: {dest} exists (--force to overwrite)")
            return 2
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(FORGE_TEMPLATE.format(name=name, desc=a.desc, when=a.when,
                                          epithet=a.epithet))
        print(f"forged {dest}")
        if a.route:
            cfg_p = os.path.join(paths.state_dir(), "config.json")
            try:
                raw = json.load(open(cfg_p, encoding="utf-8"))
            except Exception:
                raw = {}
            raw.setdefault("custom_routes", {})[a.route] = name
            json.dump(raw, open(cfg_p, "w", encoding="utf-8"), indent=2)
            print(f"route added: /{a.route}/ → {name} (custom routes beat built-ins)")
        print("next: fill in the <placeholders> in the scaffold, then restart "
              "Claude Code (or /skills) to load it")
        return 0
    if a.action == "export":
        for d in _skill_dirs(a.name_or_file):
            p = os.path.join(d, "SKILL.md")
            if os.path.isfile(p):
                out = a.out or f"{a.name_or_file}.pantheon-skill.md"
                body = open(p, encoding="utf-8").read()
                with open(out, "w", encoding="utf-8") as f:
                    f.write(f"<!-- pantheon skill export · from {p} -->\n" + body)
                print(f"exported → {out} (import with: pantheon forge import {out})")
                return 0
        print(f"forge: no skill named {a.name_or_file!r} found")
        return 2
    # import
    src = a.name_or_file
    if not os.path.isfile(src):
        print(f"forge: file not found: {src}")
        return 2
    body = open(src, encoding="utf-8").read()
    m = re.search(r"^name:\s*[\"']?([\w-]+)", body, re.M)
    if not m:
        print("forge: no `name:` in the file's frontmatter — not a skill export")
        return 2
    name = m.group(1)
    dest = os.path.join(os.path.expanduser("~"), ".claude", "skills", name, "SKILL.md")
    if os.path.isfile(dest) and not a.force:
        print(f"forge: {dest} exists (--force to overwrite)")
        return 2
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w", encoding="utf-8").write(body)
    print(f"imported {name} → {dest} (restart Claude Code to load it)")
    return 0


# ── team packs ───────────────────────────────────────────────────────────────
def cmd_pack(a):
    p = os.path.join(os.getcwd(), "pantheon.pack.json")
    if a.action == "init":
        if os.path.isfile(p) and not a.force:
            print("pack: pantheon.pack.json exists (--force to regenerate)")
            return 2
        cfg = cfgmod.load(os.getcwd())
        conn = store.connect()
        # auto-captured lessons are raw user sentences (may hold secrets/paths);
        # they stay private unless explicitly shared
        where = "" if a.include_captured else "WHERE source != 'auto' "
        top = conn.execute(
            "SELECT text,tags,keys,weight FROM lessons " + where +
            "ORDER BY weight*(uses+1) DESC, ts DESC LIMIT 20").fetchall()
        conn.close()
        pack = {"pantheon_pack": 1,
                "name": os.path.basename(os.getcwd()),
                "preset": cfg["preset"] if cfg["preset"] in ("full", "economy", "quiet") else "full",
                "overrides": {"gate": cfg["gate"], "recall": cfg["recall"]},
                "disciplines": cfg["disciplines"],
                "standards": "",
                "lessons": [dict(r) for r in top]}
        json.dump(pack, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"wrote {p} — {len(pack['lessons'])} shared lesson(s). Fill in "
              "\"standards\", commit it, and every teammate inherits this on install.")
        if not a.include_captured:
            print("(auto-captured lessons excluded — pass --include-captured to "
                  "share them; review for secrets first)")
        return 0
    path, pk = cfgmod.find_pack(os.getcwd())
    if not pk:
        print("no pantheon.pack.json found from here upward")
        return 0
    conn = store.connect()
    import hashlib
    h = hashlib.md5(json.dumps(pk, sort_keys=True).encode()).hexdigest()[:10]
    imported = h in store.get_meta(conn, "packs_imported", "").split(",")
    conn.close()
    print(f"pack: {pk.get('name', '?')} @ {path}")
    print(f"  preset {pk.get('preset', '-')} · {len(pk.get('lessons', []))} lesson(s) · "
          f"standards {'yes' if pk.get('standards') else 'no'} · "
          f"imported {'yes' if imported else 'not yet (next session start)'}")
    return 0


# ── cross-agent export ───────────────────────────────────────────────────────
CORE_SKILLS = ["ariadne", "oracle", "daedalus", "prometheus", "hydra", "argus",
               "themis", "charon", "lethe", "mnemosyne", "athena", "alexandria",
               "arachne", "dashboard", "doctor", "forge"]


def _split_frontmatter(body):
    """(description, body-without-frontmatter)."""
    desc = ""
    m = re.match(r"^---\n(.*?)\n---\n", body, re.S)
    if not m:
        return desc, body
    fm = m.group(1)
    dm = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", fm, re.M)
    if dm:
        desc = dm.group(1)
    return desc, body[m.end():]


def cmd_export(a):
    targets = ["generic", "cursor", "codex"] if a.target == "all" else [a.target]
    names = CORE_SKILLS if not a.full else sorted(
        d for d in os.listdir(os.path.join(_ROOT, "skills"))
        if os.path.isfile(os.path.join(_ROOT, "skills", d, "SKILL.md")))
    out_root = a.out or os.path.join(os.getcwd(), "pantheon-export")
    skills = []
    for n in names:
        p = os.path.join(_ROOT, "skills", n, "SKILL.md")
        if os.path.isfile(p):
            skills.append((n, open(p, encoding="utf-8").read()))
    for t in targets:
        if t == "generic":
            d = os.path.join(out_root, "generic")
            os.makedirs(d, exist_ok=True)
            for n, body in skills:
                open(os.path.join(d, f"{n}.md"), "w", encoding="utf-8").write(body)
        elif t == "cursor":
            d = os.path.join(out_root, "cursor", ".cursor", "rules")
            os.makedirs(d, exist_ok=True)
            for n, body in skills:
                desc, rest = _split_frontmatter(body)
                mdc = (f"---\ndescription: {desc[:300]}\nglobs:\nalwaysApply: false\n---\n"
                       + rest)
                open(os.path.join(d, f"pantheon-{n}.mdc"), "w", encoding="utf-8").write(mdc)
        elif t == "codex":
            d = os.path.join(out_root, "codex")
            os.makedirs(d, exist_ok=True)
            parts = ["# pantheon disciplines (exported for Codex/OpenCode-style agents)",
                     "", "Invoke by asking for a discipline by name. Sections below are "
                     "the full playbooks.", ""]
            for n, body in skills:
                _, rest = _split_frontmatter(body)
                parts += [f"\n\n---\n\n{rest.strip()}"]
            open(os.path.join(d, "AGENTS-pantheon.md"), "w", encoding="utf-8").write(
                "\n".join(parts))
    print(f"exported {len(skills)} skill(s) → {out_root} ({', '.join(targets)})")
    print("honest note: the DISCIPLINES port everywhere (they're markdown); the "
          "automation (router, recall, gate, receipts, HUD) is Claude Code-only.")
    return 0


def cmd_version(a):
    try:
        with open(os.path.join(_ROOT, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as f:
            print("pantheon v" + json.load(f).get("version", "?"))
    except Exception:
        print("pantheon (version unknown)")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="pantheon", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("receipt", help="file / list discipline receipts")
    r.add_argument("action", choices=["add", "list"])
    r.add_argument("--skill", default="")
    r.add_argument("--note", default="")
    r.add_argument("--tokens", type=int, default=0)
    r.add_argument("--days", type=float, default=7)
    r.add_argument("--limit", type=int, default=30)
    r.set_defaults(fn=cmd_receipt)

    l = sub.add_parser("lesson", help="add / list / search / import-inbox")
    l.add_argument("action", choices=["add", "list", "search", "import-inbox"])
    l.add_argument("text", nargs="?", default="")
    l.add_argument("--tags", default="")
    l.add_argument("--keys", default="")
    l.add_argument("--weight", type=float, default=1.3)
    l.add_argument("--limit", type=int, default=20)
    l.set_defaults(fn=cmd_lesson)

    rc = sub.add_parser("recall", help="debug: what auto-recall would surface")
    rc.add_argument("text")
    rc.set_defaults(fn=cmd_recall)

    st = sub.add_parser("stats", help="counts, top disciplines, spend")
    st.set_defaults(fn=cmd_stats)

    d = sub.add_parser("dashboard", help="live TUI (or --plain)")
    d.add_argument("--plain", action="store_true")
    d.set_defaults(fn=cmd_dashboard)

    dr = sub.add_parser("doctor", help="diagnose + fix the install")
    dr.add_argument("--fix", action="store_true")
    dr.set_defaults(fn=cmd_doctor)

    f = sub.add_parser("forge", help="scaffold / share custom disciplines")
    f.add_argument("action", choices=["new", "export", "import"])
    f.add_argument("name_or_file")
    f.add_argument("--desc", default="A custom discipline.")
    f.add_argument("--when", default="the user asks for it")
    f.add_argument("--epithet", default="a discipline of your own")
    f.add_argument("--route", default="", help="regex that auto-routes to it")
    f.add_argument("--project", action="store_true",
                   help="scaffold into ./.claude/skills instead of ~/.claude/skills")
    f.add_argument("--out", default="")
    f.add_argument("--force", action="store_true")
    f.set_defaults(fn=cmd_forge)

    pk = sub.add_parser("pack", help="team pack in this repo")
    pk.add_argument("action", choices=["init", "status"])
    pk.add_argument("--force", action="store_true")
    pk.add_argument("--include-captured", action="store_true",
                    help="also share auto-captured lessons (review for secrets first)")
    pk.set_defaults(fn=cmd_pack)

    ex = sub.add_parser("export", help="package disciplines for other agents")
    ex.add_argument("--target", choices=["generic", "cursor", "codex", "all"],
                    default="all")
    ex.add_argument("--out", default="")
    ex.add_argument("--full", action="store_true",
                    help="export ALL bundled skills, not just the core 16")
    ex.set_defaults(fn=cmd_export)

    v = sub.add_parser("version")
    v.set_defaults(fn=cmd_version)
    return ap


def main(argv):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


def selftest() -> int:
    ap = build_parser()
    a = ap.parse_args(["receipt", "add", "--skill", "hydra", "--note", "x"])
    assert a.fn is cmd_receipt and a.skill == "hydra"
    a = ap.parse_args(["lesson", "add", "some text", "--tags", "t"])
    assert a.fn is cmd_lesson and a.text == "some text"
    a = ap.parse_args(["dashboard", "--plain"])
    assert a.fn is cmd_dashboard and a.plain
    a = ap.parse_args(["doctor", "--fix"])
    assert a.fn is cmd_doctor and a.fix
    a = ap.parse_args(["forge", "new", "deploy-ritual", "--route", "deploy to prod"])
    assert a.fn is cmd_forge and a.route == "deploy to prod"
    a = ap.parse_args(["export", "--target", "cursor"])
    assert a.fn is cmd_export and not a.full
    a = ap.parse_args(["pack", "init"])
    assert a.fn is cmd_pack and not a.include_captured
    a = ap.parse_args(["pack", "init", "--include-captured"])
    assert a.include_captured
    assert _age(time.time() - 30) == "0m" and _age(time.time() - 90000) == "1d"
    s1, s7 = _spend()
    assert s1 >= 0 and s7 >= s1
    # frontmatter splitter feeds the cursor/codex exports
    desc, rest = _split_frontmatter('---\nname: x\ndescription: "does x"\n---\n# body\n')
    assert desc == "does x" and rest.startswith("# body")
    assert _split_frontmatter("no frontmatter")[1] == "no frontmatter"
    # forge template renders with a receipt line and announce block
    t = FORGE_TEMPLATE.format(name="zz", desc="d", when="w", epithet="e")
    assert "name: zz" in t and "receipt add --skill zz" in t and "🏛 **zz**" in t
    print("selftest ok — parser wiring, age fmt, spend reader, forge/export helpers")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main(sys.argv[1:]))
