#!/usr/bin/env python3
"""modus learning-capture hook (Stop event).

Appends each turn's user signal to a learning inbox so corrections and
preferences can be consolidated into durable memory later (see the
`memory-loop` skill). This is the safety net; disciplined in-conversation
capture is primary.

Design constraints:
- NEVER break the session: any failure exits 0 silently.
- No network, no external deps, stdlib only.
- Writes to <project>/.modus/learning-inbox.md when run inside a project,
  else ~/.claude/modus/learning-inbox.md.

Self-check:  python3 capture-learning.py --selftest
"""
import sys, os, json, re, datetime

# Phrases that suggest the user is correcting or redirecting — worth a closer
# look during consolidation. Deliberately broad; consolidation drops the noise.
CORRECTION = re.compile(
    r"\b(no|not|don'?t|stop|wrong|actually|instead|isn'?t|aren'?t|"
    r"i said|i told you|you (didn'?t|did not|forgot|missed|keep)|"
    r"why (did|are|is)|that'?s not|never|again|still (not|doesn'?t|broken))\b",
    re.IGNORECASE,
)


def inbox_path(cwd: str) -> str:
    """Project-local inbox if in a project, else a user-global one."""
    if cwd and os.path.isdir(cwd):
        return os.path.join(cwd, ".modus", "learning-inbox.md")
    return os.path.join(os.path.expanduser("~"), ".claude", "modus", "learning-inbox.md")


def last_user_text(transcript_path: str) -> str:
    """Pull the most recent user message text from a JSONL transcript."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    text = ""
    with open(transcript_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("role") == "user" or obj.get("type") == "user":
                content = obj.get("content") or obj.get("message", {}).get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        p.get("text", "") for p in content if isinstance(p, dict)
                    )
                if isinstance(content, str) and content.strip():
                    text = content.strip()
    return text


def append(path: str, line: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd") or os.getcwd()
    text = last_user_text(payload.get("transcript_path", ""))
    if not text:
        return 0
    flag = " ⚠️ likely-correction" if CORRECTION.search(text) else ""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    snippet = " ".join(text.split())[:280]
    append(inbox_path(cwd), f"- [{stamp}]{flag} {snippet}\n")
    return 0


def selftest() -> int:
    assert CORRECTION.search("no, that's wrong")
    assert CORRECTION.search("you forgot to save it")
    assert CORRECTION.search("why did you do that")
    assert not CORRECTION.search("please add a dark theme toggle")
    assert not CORRECTION.search("thanks, that works great")
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except Exception:
        # A hook must never break the session.
        raise SystemExit(0)
