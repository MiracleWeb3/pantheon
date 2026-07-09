<div align="center">

# 🏛 pantheon

**One install. Thirteen disciplines. Your coding agent stops winging it.**

*A problem-solving method for [Claude Code](https://claude.com/claude-code) — it reads your prompt, picks the right discipline, tells you what it's about to do, and does it the way a careful senior engineer would.*

![version](https://img.shields.io/badge/version-0.5.0-6f42c1) ![license](https://img.shields.io/badge/license-MIT-blue) ![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-d97757) ![deps](https://img.shields.io/badge/dependencies-none-brightgreen)

</div>

---

Most agent mistakes aren't capability failures — they're **sequencing** failures: editing before understanding the code, calling an API from memory that changed three versions ago, self-approving a broken diff, over-building what didn't need to exist, forgetting the correction you gave two messages ago. Raw intelligence doesn't fix these. **Discipline does.**

`pantheon` is that discipline, packaged. Ten skills, each named for the myth that fits, each a countermeasure to one failure mode. It's **automatic** (a router fires the right one from plain language), **transparent** (each announces itself before acting), and **composable** (it makes oh-my-claudecode, superpowers, and graphify sharper — it never forks them).

```bash
claude plugin marketplace add MiracleWeb3/pantheon
claude plugin install pantheon@pantheon
```

Restart Claude Code. That's it — it starts working on your next prompt.

## What makes it different

**🎯 It's automatic.** You don't memorize commands. Type *"this bug keeps coming back"* and the `hydra` discipline takes over — root-cause first, reproduce, fix at the root, seal with a regression test. Type *"build the export feature properly"* and `daedalus` runs the quality gates. A prompt-router hook reads intent and fires the match; you can always invoke one by hand (`/pantheon:hydra`), and an explicit call always wins.

**🗣 It announces itself.** When a discipline activates — by your hand or the router's — it opens with one line: *which* power took over, *what* it understood your goal to be, and the *steps* it's about to take. You see the plan **before** any work happens, and can redirect. No silent automation.

> 🏛 **hydra** — slay it, then cauterize. **Task:** the timestamp bug that reappears after each deploy. **Plan:** reproduce against real data → trace the inbound clock path → fix the shared carry, not the caller → add a regression test that fails on the old code.

**🧩 It composes, never clones.** Every skill uses richer tools when you have them and falls back to first principles when you don't. Nothing is vendored or copied — pantheon is the *conductor*, your other plugins are the orchestra.

**🧠 It remembers.** A learning loop captures your corrections and preferences the moment they land, consolidates them into durable memory, and promotes what recurs into always-loaded rules. Your agent gets more *yours* every session.

**📊 It has a HUD.** An optional statusline shows the active discipline, model, branch, unconsolidated-lessons count, and session cost — one calm line.

**⚙️ It's configurable.** Full experience by default; flip to **economy** (no announce prose, soft routing — save tokens) or **quiet** (fully manual), globally or per-project. Turn off any discipline you don't want. Just say *"set pantheon to economy mode."*

## The pantheon

Mythical names, plain-English triggers. Read top-to-bottom and it *is* the lifecycle of a change.

| Skill | Say | The discipline |
|---|---|---|
| 🧵 **`ariadne`** | *"how does this work?"* | **Orient** — read the code-map, past decisions, and prior lessons *before* editing. The thread through the labyrinth. |
| 🕸 **`arachne`** | *"map the codebase"* | **Map** — weave a navigable knowledge graph (nodes, edges, god-nodes) so orientation is a query, not a grep. Builds what `ariadne` reads. |
| 🔮 **`oracle`** | *"how do I use X?"* | **Research** — consult the real docs before an unfamiliar SDK/API. Never code a contract from memory. |
| 🏗 **`daedalus`** | *"build this right"* | **Build** — scope → plan → challenge the plan → build → review with a different lens. |
| 🦉 **`athena`** | *"design the UI"* | **Craft** — interface work with real hierarchy, spacing, type, states, and accessibility. Intentional, never templated. |
| 🔥 **`prometheus`** | *"test first"* | **Test-first** — the failing test before the code. Red → green → refactor. |
| 🐉 **`hydra`** | *"this bug is nasty"* | **Debug** — root cause before fix, reproduce before editing, cauterize with a regression test. |
| 👁 **`argus`** | *"this is huge"* | **Decompose** — split a too-big task, fan out one fresh-context worker per slice, synthesize. |
| ⚖️ **`themis`** | *"review this"* | **Review** — adversarial, severity-ranked, self-verified. The reviewer is never the author. |
| ⛴ **`charon`** | *"land it"* | **Ship** — atomic commits, a clean PR, branch hygiene. Never ships unasked. |
| 🌊 **`lethe`** | *"keep it simple"* | **Simplify** — YAGNI, stdlib before custom, native before dependency, deletion over addition. |
| 📜 **`mnemosyne`** | *"remember this"* | **Learn** — capture corrections, consolidate to memory, promote what recurs into always-loaded rules. |
| 📚 **`alexandria`** | *"document this"* | **Knowledge** — a curated project wiki (the Karpathy LLM-wiki model) whose prose compounds across sessions. |

> **Three knowledge layers, unified.** `arachne` maps the *structure* (your graphify graph), `alexandria` records the *prose* (your Obsidian/ADR wiki — the "why"), and `mnemosyne` holds the *facts* (your memory bank of corrections). `ariadne` reads all three to orient before any work. Graph + wiki + memory, one method.

## The two ideas underneath

1. **Separate your passes.** Understand ≠ plan ≠ build ≠ verify, and the reviewer is never the author. `daedalus` and `hydra` are the same rigor pointed at opposite problem *shapes* — building vs. diagnosing — which is why they run nearly opposite sequences.
2. **Match the tool to the shape.** A feature is a *planning* problem. A hard bug is a *diagnosis* problem. A giant task is a *decomposition* problem. Reaching for the wrong shape — a heavy build-pipeline on a one-line bug, a single context on a repo-wide migration — is the most common misroute. pantheon names the fork so you take the right branch.

## Composes with your stack — never replaces it

`pantheon` is a **method, not a monolith**. It orchestrates these when present and does the steps by hand when not:

- **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** — `daedalus` drives its `deep-interview → ralplan → autopilot` pipeline; `hydra` uses its `tracer` agent and `ralph` loop; `argus` uses its Workflow engine.
- **[superpowers](https://github.com/anthropics/claude-plugins-official)** — `daedalus` uses `brainstorming → writing-plans → verification-before-completion`; `prometheus` uses `test-driven-development`; `hydra` uses `systematic-debugging`.
- **A code map** ([graphify](https://github.com/) or any repo map) — `ariadne` queries it before grepping.
- **A decisions wiki** (Obsidian, `docs/adr/`) — `ariadne` reads it to learn *why* the code is the way it is.

With none installed, every skill still works.

## Configuration

pantheon runs full-strength out of the box. Want it leaner — or fully manual? Drop a `config.json` at `~/.claude/pantheon/config.json` (global) or `<project>/.pantheon/config.json` (per-project, wins):

```json
{ "preset": "economy" }
```

| Preset | Routing | Announce block | For |
|---|---|---|---|
| `full` *(default)* | on — auto-fires the right skill | shown | the whole experience |
| `economy` | soft one-line suggestions only | **hidden** | saving tokens — no announce prose, terse output |
| `quiet` | **off** — you invoke skills yourself | hidden | full manual control |

Override any single knob, or switch off a discipline you never want:

```json
{ "routing": "suggest", "announce": false, "disciplines": { "athena": false } }
```

Or just tell your agent *"set pantheon to economy mode"* — it writes the file for you.

## The HUD (optional)

Add to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "python3 ~/.claude/plugins/marketplaces/pantheon/scripts/hud.py"
}
```

```
🏛 · hydra · Fable 5 · ⎇ main · 📥 3 · $0.42
```

Active discipline · model · branch · unconsolidated lessons · session cost.

## Under the hood

- **Three hooks, stdlib-only, fail-silent.** `route.py` (UserPromptSubmit) auto-routes; `capture-learning.py` (Stop) feeds the memory loop; `session-start.py` injects your config once per session. A broken hook never breaks your session.
- **Zero dependencies.** No npm, no pip, no build step. Skills are Markdown; hooks and HUD are plain Python 3.
- **Every hook and HUD ships a self-check** — `python3 hooks/route.py --selftest`, etc.

## License

MIT — see [LICENSE](LICENSE). Independent work; the tools it composes with belong to their respective authors, and are credited, not copied.

<div align="center"><sub>Built for people who want their agent to work like an engineer, not a slot machine.</sub></div>
