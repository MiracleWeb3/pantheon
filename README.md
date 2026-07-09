# modus

**A disciplined problem-solving method for [Claude Code](https://claude.com/claude-code), as a plugin.**

Most agent mistakes aren't capability failures — they're *sequencing* failures: acting before understanding, planning what isn't understood, self-approving work in the same breath it was written, and forgetting the correction you just got. `modus` encodes four habits that prevent those, and wires them to whatever planning/debugging tools you already have.

The whole method in one line: **orient before you act, match the tool to the problem's shape, keep your passes separate, and compound what you learn.**

## The four skills

| Skill | Use it when | What it does |
|---|---|---|
| **`orient`** | Before touching unfamiliar code | Read the structure map + past decisions + prior lessons *before* editing. Grepping blind is the anti-pattern. |
| **`ship`** | Vague idea → feature, done right | Runs the quality gates in order: scope → plan → challenge the plan → build → review with a *different lens*. |
| **`hardbug`** | A bug that resists the obvious fix | Diagnosis-first: root cause before fix, reproduce before editing, then lock it with a regression test. |
| **`memory-loop`** | The user corrects you or states a preference | Capture it now, consolidate into durable memory, promote what recurs into always-loaded rules. |

The unifying principle is **separate passes**: understand ≠ plan ≠ build ≠ verify, and the reviewer is never the author. `ship` and `hardbug` are the same discipline pointed at two different problem *shapes* — building vs. diagnosing — which is why they run almost opposite sequences.

## Why match the tool to the shape

A feature and a bug fail differently, so they need opposite openings:

- **Building** is a *planning* problem → `ship` front-loads scoping and plan-review, because the risk is building the wrong thing well.
- **A hard bug** is a *diagnosis* problem → `hardbug` refuses to plan a fix at all until the mechanism is found, because the risk is fixing a symptom confidently.

Reaching for the heavy build-pipeline on a bug (or hand-waving a hard bug as a "quick fix") is the most common misroute. `modus` names the fork so you take the right branch.

## Install

```bash
claude plugin marketplace add OWNER/modus
claude plugin install modus@modus
```

Restart Claude Code. The skills auto-route on their descriptions, or invoke explicitly: `/modus:ship`, `/modus:hardbug`, `/modus:orient`, `/modus:memory-loop`.

## Optional integrations (it degrades gracefully without them)

`modus` is a **method**, not a monolith — each skill uses richer tools when present and falls back when not:

- **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** — `ship` uses its `deep-interview → ralplan → autopilot` consensus pipeline; `hardbug` uses its `tracer` agent and `ralph` verification loop.
- **[superpowers](https://github.com/anthropics/claude-plugins-official)** — `ship` uses `brainstorming → writing-plans → verification-before-completion`; `hardbug` uses `systematic-debugging`.
- **A code map** (e.g. [graphify](https://github.com/)) — `orient` queries it before grepping.
- **A decisions wiki** (Obsidian vault, `docs/adr/`, …) — `orient` reads it to learn *why* the code is the way it is.

With none of these installed, every skill still works — it just does the steps by hand.

## The learning hook

A `stop` hook (`hooks/capture-learning.py`, stdlib-only, fails silent) appends each turn's user signal to a `learning-inbox.md`, flagging likely corrections. It's the safety net under `memory-loop`'s in-conversation capture. Self-check: `python3 hooks/capture-learning.py --selftest`.

## License

MIT — see [LICENSE](LICENSE).
