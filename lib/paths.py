#!/usr/bin/env python3
"""pantheon shared paths — one place that knows where runtime state lives.

Everything under ~/.claude/pantheon/ :
  pantheon.db          the SQLite store (lessons/receipts/routes/metrics/meta)
  bin/pantheon         CLI shim (refreshed each SessionStart, points at the
                       currently-installed plugin root)
  *.json / *.jsonl     small caches and the spend ledger (owned by hud.py)

stdlib only, fail-soft: path helpers never raise.
Self-check: python3 paths.py --selftest
"""
import os

def state_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".claude", "pantheon")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def db_path() -> str:
    return os.path.join(state_dir(), "pantheon.db")


def bin_dir() -> str:
    d = os.path.join(state_dir(), "bin")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def shim_path() -> str:
    return os.path.join(bin_dir(), "pantheon")


def plugin_root() -> str:
    """The installed plugin root: $CLAUDE_PLUGIN_ROOT when a hook set it,
    else derived from this file's location (<root>/lib/paths.py)."""
    r = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if r and os.path.isdir(r):
        return r
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_name(cwd: str) -> str:
    """Short project key for scoping lessons/receipts. '' when unknown."""
    try:
        return os.path.basename(str(cwd).rstrip("/")) if cwd else ""
    except Exception:
        return ""


def selftest() -> int:
    assert state_dir().endswith("pantheon")
    assert db_path().endswith("pantheon.db")
    assert shim_path().endswith(os.path.join("bin", "pantheon"))
    root = plugin_root()
    assert os.path.isdir(root), root
    assert project_name("/a/b/parserx") == "parserx" and project_name("") == ""
    print("selftest ok —", state_dir())
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
