#!/usr/bin/env python3
"""pantheon HUD — a statusline for Claude Code.

One calm line: active discipline · model · git branch · learning-inbox count · cost.

Setup (one snippet in ~/.claude/settings.json — the marketplace path is stable
across plugin updates):

    "statusLine": {
      "type": "command",
      "command": "python3 ~/.claude/plugins/marketplaces/pantheon/scripts/hud.py"
    }

Design constraints: stdlib only, fail-silent (a broken statusline is worse than
none), no subprocesses (reads .git/HEAD directly — fast every render).
Self-check:  python3 hud.py --selftest
"""
import sys, os, json, datetime

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
YELLOW = "\033[33m"
RESET = "\033[0m"

ROUTE_TTL_HOURS = 4


def git_branch(cwd: str) -> str:
    """Read the branch from .git/HEAD without spawning git. Worktree-aware."""
    d = cwd
    for _ in range(12):  # walk up at most 12 levels
        head = os.path.join(d, ".git", "HEAD")
        gitfile = os.path.join(d, ".git")
        if os.path.isfile(gitfile) and not os.path.isdir(gitfile):
            # worktree: ".git" is a file "gitdir: <path>"
            with open(gitfile, encoding="utf-8") as f:
                line = f.read().strip()
            if line.startswith("gitdir:"):
                head = os.path.join(line.split(":", 1)[1].strip(), "HEAD")
        if os.path.isfile(head):
            with open(head, encoding="utf-8") as f:
                ref = f.read().strip()
            return ref.rsplit("/", 1)[-1] if ref.startswith("ref:") else ref[:8]
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return ""


def last_route() -> str:
    """The discipline routed most recently, if fresh enough."""
    p = os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "last-route.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        at = datetime.datetime.fromisoformat(d["at"])
        if (datetime.datetime.now() - at).total_seconds() < ROUTE_TTL_HOURS * 3600:
            return d.get("skill", "")
    except Exception:
        pass
    return ""


def inbox_count(cwd: str) -> int:
    """Unconsolidated learning-inbox lines (project + global)."""
    n = 0
    for p in (os.path.join(cwd, ".pantheon", "learning-inbox.md"),
              os.path.join(os.path.expanduser("~"), ".claude", "pantheon", "learning-inbox.md")):
        try:
            with open(p, encoding="utf-8") as f:
                n += sum(1 for line in f if line.lstrip().startswith("-"))
        except Exception:
            pass
    return n


def build_line(payload: dict) -> str:
    cwd = (payload.get("workspace") or {}).get("current_dir") or payload.get("cwd") or os.getcwd()
    model = (payload.get("model") or {}).get("display_name") or ""
    cost = (payload.get("cost") or {}).get("total_cost_usd")

    parts = [f"{MAGENTA}🏛{RESET}"]
    skill = last_route()
    if skill:
        parts.append(f"{BOLD}{MAGENTA}{skill}{RESET}")
    if model:
        parts.append(f"{CYAN}{model}{RESET}")
    branch = git_branch(cwd)
    if branch:
        parts.append(f"{DIM}⎇ {branch}{RESET}")
    inbox = inbox_count(cwd)
    if inbox:
        parts.append(f"{YELLOW}📥 {inbox}{RESET}")
    if isinstance(cost, (int, float)) and cost > 0:
        parts.append(f"{DIM}${cost:.2f}{RESET}")
    return f" {DIM}·{RESET} ".join(parts)


def chained_line(raw: str, cmd: str) -> str:
    """Run another statusline command with the same payload; its line comes
    first, pantheon's segment is appended. Their HUD stays primary."""
    import subprocess
    try:
        r = subprocess.run(cmd, shell=True, input=raw.encode(),
                           capture_output=True, timeout=3)
        other = r.stdout.decode(errors="replace").strip().splitlines()
        return other[0] if other else ""
    except Exception:
        return ""


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    mine = build_line(payload)
    if "--chain" in sys.argv:
        i = sys.argv.index("--chain")
        cmd = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        other = chained_line(raw, cmd) if cmd else ""
        if other:
            print(f"{other} {DIM}·{RESET} {mine}")
            return 0
    print(mine)
    return 0


def selftest() -> int:
    fake = {"model": {"display_name": "Fable 5"},
            "workspace": {"current_dir": os.getcwd()},
            "cost": {"total_cost_usd": 1.234}}
    line = build_line(fake)
    assert "Fable 5" in line and "🏛" in line and "$1.23" in line
    assert git_branch("/nonexistent/path") == ""      # no crash off-repo
    assert isinstance(inbox_count("/nonexistent"), int)
    other = chained_line("{}", "echo OTHER-HUD")
    assert other == "OTHER-HUD", other                 # chaining keeps their HUD
    assert chained_line("{}", "exit 1") == ""          # broken chain → just ours
    print("selftest ok —", line)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        print("🏛")  # a broken statusline is worse than a plain one
        raise SystemExit(0)
