# pantheon

**A disciplined problem-solving method for [Claude Code](https://claude.com/claude-code) and other coding agents — a small pantheon of skills, each a named power.**

Most agent mistakes aren't capability failures — they're *sequencing* failures: acting before understanding, planning what isn't understood, self-approving work in the same breath it was written, over-building what didn't need to exist, and forgetting the correction you just got. `pantheon` gives each of those failure modes a countermeasure, names it after the myth that fits, and wires it to whatever tools you already have.

The whole method in one line: **orient before you act, match the tool to the problem's shape, do the least that works, and compound what you learn.**

## The pantheon

Mythical names, plain-English triggers — each skill auto-fires on natural language *and* explains itself.

| Skill | Say | What it does |
|---|---|---|
| **`ariadne`** | *"how does this work?"* | The thread through the labyrinth: read the code-map + past decisions + prior lessons **before** editing. Grepping blind is the anti-pattern. |
| **`oracle`** | *"how do I use X?"* | The Delphic oracle: consult the real docs before using an unfamiliar SDK or API — never code it from memory. |
| **`daedalus`** | *"build this right"* | The master craftsman: scope → plan → challenge the plan → build → review with a **different lens**. |
| **`prometheus`** | *"test first"* | Foresight: the failing test written before the code. Red → green → refactor. |
| **`hydra`** | *"this bug is nasty"* | Slay it, then cauterize: root cause before fix, reproduce before editing, seal it with a regression test so the head can't grow back. |
| **`argus`** | *"this is huge"* | The hundred eyes: decompose a too-big task, fan out one fresh-context subagent per slice, synthesize. (The RLM / divide-and-conquer discipline.) |
| **`themis`** | *"review this"* | The scales of judgment: an independent, adversarial review pass — correctness, security, quality — where the reviewer is never the author. |
| **`charon`** | *"land it"* | The ferryman: clean atomic commits, a well-formed PR, finish-the-branch hygiene. Ships only when asked. |
| **`lethe`** | *"simplest thing that works"* | The river of forgetting: YAGNI, stdlib before custom, native before dependency, one line before fifty, deletion before addition. |
| **`mnemosyne`** | *"remember this"* | The mother of memory: capture corrections the moment they land, consolidate into durable memory, promote what recurs into always-loaded rules. Ships the learning hook. |

## The idea behind it

Two principles unify the pantheon:

1. **Separate your passes.** Understand ≠ plan ≠ build ≠ verify, and the reviewer is never the author. `daedalus` and `hydra` are the same discipline pointed at opposite problem *shapes* — building vs. diagnosing — which is why they run nearly opposite sequences.
2. **Match the tool to the shape.** A feature is a *planning* problem (front-load scope + plan-review). A hard bug is a *diagnosis* problem (refuse to plan a fix until the mechanism is found). A too-big task is a *decomposition* problem (`argus`). Reaching for the wrong shape — a heavy build-pipeline on a bug, a lone context on a repo-wide migration — is the most common misroute. `pantheon` names the fork so you take the right branch.

## Composes with your stack — never replaces it

`pantheon` is a **method, not a monolith**. Each skill uses richer tools when they're installed and falls back to first principles when they're not. It orchestrates these; it does not fork or vendor them:

- **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** — `daedalus` drives its `deep-interview → ralplan → autopilot` pipeline; `hydra` uses its `tracer` agent and `ralph` verification loop; `argus` uses its Workflow engine.
- **[superpowers](https://github.com/anthropics/claude-plugins-official)** — `daedalus` uses `brainstorming → writing-plans → verification-before-completion`; `hydra` uses `systematic-debugging`.
- **A code map** ([graphify](https://github.com/) or similar) — `ariadne` queries it before grepping.
- **A decisions wiki** (Obsidian, `docs/adr/`) — `ariadne` reads it to learn *why* the code is the way it is.

With none installed, every skill still works — it just does the steps by hand.

## Install

```bash
claude plugin marketplace add MiracleWeb3/pantheon
claude plugin install pantheon@pantheon
```

Restart Claude Code. Skills auto-route on their descriptions, or invoke explicitly: `/pantheon:ariadne`, `/pantheon:oracle`, `/pantheon:daedalus`, `/pantheon:prometheus`, `/pantheon:hydra`, `/pantheon:argus`, `/pantheon:themis`, `/pantheon:charon`, `/pantheon:lethe`, `/pantheon:mnemosyne`.

## The learning hook

A `Stop` hook (`hooks/capture-learning.py`, stdlib-only, fails silent) appends each turn's user signal to a `learning-inbox.md`, flagging likely corrections — the net under `mnemosyne`'s in-conversation capture. Self-check: `python3 hooks/capture-learning.py --selftest`.

## License

MIT — see [LICENSE](LICENSE). Independent work; the tools it composes with are the property of their respective authors.
