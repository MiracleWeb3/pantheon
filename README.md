<div align="center">

<img src="assets/banner.svg" alt="pantheon — disciplines for coding agents" width="660">

### One install. Your coding agent stops winging it.

13 disciplines + 170 skills from the best open-source plugins, merged into one — for [Claude Code](https://claude.com/claude-code).

![version](https://img.shields.io/badge/version-0.7.0-8957e5?style=flat-square) &nbsp;![license](https://img.shields.io/badge/license-MIT-3fb950?style=flat-square) &nbsp;![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-d97757?style=flat-square) &nbsp;![dependencies](https://img.shields.io/badge/dependencies-none-3fb950?style=flat-square) &nbsp;![skills](https://img.shields.io/badge/skills-185-8957e5?style=flat-square)

</div>

---

Most agent mistakes aren't capability failures — they're **sequencing** failures: editing before understanding the code, calling an API from memory that changed three versions ago, self-approving a broken diff, over-building what didn't need to exist, forgetting the correction you gave two messages ago. Raw intelligence doesn't fix these. **Discipline does.**

`pantheon` is that discipline, packaged. 13 core disciplines, each named for the myth that fits, each a countermeasure to one failure mode — **automatic** (a router fires the right one from plain language) and **transparent** (each announces itself before acting). On top, it **merges in** the best open-source plugins (superpowers, ponytail, oh-my-claudecode, ui-skills — attributed, licenses kept), so one install gives you everything.

```bash
claude plugin marketplace add MiracleWeb3/pantheon
claude plugin install pantheon@pantheon
```

Restart Claude Code. That's it — it starts working on your next prompt.

## What makes it different

**🎯 It's automatic.** You don't memorize commands. Type *"this bug keeps coming back"* and the `hydra` discipline takes over — root-cause first, reproduce, fix at the root, seal with a regression test. Type *"build the export feature properly"* and `daedalus` runs the quality gates. A prompt-router hook reads intent and fires the match; you can always invoke one by hand (`/pantheon:hydra`), and an explicit call always wins.

**🗣 It announces itself.** When a discipline activates — by your hand or the router's — it opens with one line: *which* power took over, *what* it understood your goal to be, and the *steps* it's about to take. You see the plan **before** any work happens, and can redirect. No silent automation.

> 🏛 **hydra** — slay it, then cauterize. **Task:** the timestamp bug that reappears after each deploy. **Plan:** reproduce against real data → trace the inbound clock path → fix the shared carry, not the caller → add a regression test that fails on the old code.

**🧩 Everything, in one install.** The 13 core disciplines stand alone (no dependencies), and on top pantheon vendors in the full skill sets of the best open-source plugins — every one attributed in `CREDITS.md` with its license retained in `LICENSES/`. Uninstall the rest; this has it.

**🧠 It remembers.** A learning loop captures your corrections and preferences the moment they land, consolidates them into durable memory, and promotes what recurs into always-loaded rules. Your agent gets more *yours* every session.

**📊 It has a real HUD.** An optional statusline that beats the defaults: active discipline, model, **reasoning effort**, **session time**, **live context fill %**, lines changed, session cost, and **rolling hourly + weekly spend** — the last two tracked by pantheon itself because Claude Code doesn't expose them.

**⚙️ It's configurable.** Full experience by default; flip to **economy** (no announce prose, soft routing — save tokens) or **quiet** (fully manual), globally or per-project. Turn off any discipline you don't want. Just say *"set pantheon to economy mode."*

**🔔 It tells you when it's updated.** Once a day (fail-silent, cached, 2s timeout) it checks GitHub for a newer version and surfaces a one-line heads-up with the update command — no telemetry, no phone-home beyond that version check, and off with `"updateCheck": false`.

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

## Everything, merged in

pantheon doesn't just *point at* the best open-source plugins — it **vendors them in**, so one install gives you all of it. On top of the 13 core disciplines, it bundles the full skill sets of:

- **[superpowers](https://github.com/anthropics/claude-plugins-official)** (Jesse Vincent, MIT) — brainstorming, systematic-debugging, TDD, plan writing/execution, parallel agents, git worktrees, and more.
- **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** (Yeachan Heo, MIT) — its full skill catalog.
- **[ponytail](https://github.com/DietrichGebert/ponytail)** (Dietrich Gebert, MIT) — the lazy-senior-dev discipline set.
- **[ui-skills](https://www.ui-skills.com/) & design collections** — frontend-design, interface-design, animation, three.js, framework skills.

Every vendored skill keeps its original license (see [`LICENSES/`](LICENSES/)) and is attributed in [`CREDITS.md`](CREDITS.md). All rights remain with the original authors. Don't want the bulk? `economy`/`quiet` config and per-skill `disciplines` toggles keep it lean.

## The two ideas underneath

1. **Separate your passes.** Understand ≠ plan ≠ build ≠ verify, and the reviewer is never the author. `daedalus` and `hydra` are the same rigor pointed at opposite problem *shapes* — building vs. diagnosing — which is why they run nearly opposite sequences.
2. **Match the tool to the shape.** A feature is a *planning* problem. A hard bug is a *diagnosis* problem. A giant task is a *decomposition* problem. Reaching for the wrong shape — a heavy build-pipeline on a one-line bug, a single context on a repo-wide migration — is the most common misroute. pantheon names the fork so you take the right branch.

## Composes with your stack — never replaces it

`pantheon` is a **method, not a monolith**. It orchestrates these when present and does the steps by hand when not:

- **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** — `daedalus` drives its `deep-interview → ralplan → autopilot` pipeline; `hydra` uses its `tracer` agent and `ralph` loop; `argus` uses its Workflow engine.
- **[superpowers](https://github.com/anthropics/claude-plugins-official)** — `daedalus` uses `brainstorming → writing-plans → verification-before-completion`; `prometheus` uses `test-driven-development`; `hydra` uses `systematic-debugging`.
- **A code map** ([graphify](https://github.com/) or any repo map) — `ariadne` queries it before grepping.
- **A decisions wiki** (Obsidian, `docs/adr/`) — `ariadne` / `alexandria` read and write it.
- **Design skills** ([ui-skills](https://www.ui-skills.com/), `frontend-design`, `shadcn`, …) — `athena` drives whichever you have installed and reviews the output against its craft standard. It is the art-director, **not** a bundled copy of those collections.

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

Override any single knob, switch off a discipline, or silence update checks:

```json
{ "routing": "suggest", "announce": false, "disciplines": { "athena": false }, "updateCheck": false }
```

| Knob | Values | Default |
|---|---|---|
| `routing` | `on` · `suggest` · `off` | `on` |
| `announce` | `true` · `false` | `true` |
| `disciplines` | `{ "<skill>": false }` | all on |
| `updateCheck` | `true` · `false` | `true` |

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
🏛 · hydra · Fable 5 · ✳max · ⧗2h35m · ▓47% · +420/-95 · $6.80 · ⧖1h $2.10 · wk $18.40 · ⎇ main · 📥3
```

Every segment is real data, shown only when it has a value:

| Segment | Meaning | Source |
|---|---|---|
| `hydra` | active discipline | pantheon router |
| `Fable 5` | model | payload |
| `✳max` | reasoning effort | parsed from `/effort` in the transcript |
| `⧗2h35m` | session wall-clock | `cost.total_duration_ms` |
| `▓47%` | **live context fill** | last turn's real token `usage` (not file size) |
| `+420/-95` | lines added / removed | `cost.total_lines_*` |
| `$6.80` | this session's cost | `cost.total_cost_usd` |
| `⧖1h $2.10` · `wk $18.40` | **rolling hourly / weekly spend** | pantheon's own cost-delta ledger |
| `⎇ main` · `📥3` | branch · unconsolidated lessons | `.git/HEAD` · learning-inbox |

The **hourly/weekly spend** and **live context %** are things Claude Code doesn't hand a statusline — pantheon derives them: it diffs cumulative session cost over time into an hour/week ledger, and reads the actual `input + cache` token count from the latest transcript record for a true context gauge. `▓` goes green → yellow → red as context fills, and flips to `ctx>200k` past the window.

**Already have a statusline** (from another plugin or your own)? Claude Code allows one `statusLine`, so pantheon won't silently fight it — you choose:

- **Keep yours** — skip the HUD entirely; every other pantheon feature works without it.
- **Chain both** — point `statusLine` at pantheon with `--chain` and your existing command; your line renders first, pantheon's segment appends:

```json
"statusLine": {
  "type": "command",
  "command": "python3 ~/.claude/plugins/marketplaces/pantheon/scripts/hud.py --chain 'your-existing-statusline-command'"
}
```

If your command errors, pantheon shows just its own segment — never a blank bar.

## Under the hood

- **Three hooks, stdlib-only, fail-silent.** `route.py` (UserPromptSubmit) auto-routes; `capture-learning.py` (Stop) feeds the memory loop; `session-start.py` injects your config once per session. A broken hook never breaks your session.
- **Zero dependencies.** No npm, no pip, no build step. Skills are Markdown; hooks and HUD are plain Python 3.
- **Every hook and HUD ships a self-check** — `python3 hooks/route.py --selftest`, etc.

## Roadmap

pantheon is early and moving fast — **12 features across four releases**: retrieval-augmented memory that surfaces the right past lesson at the right moment, per-discipline receipts, a TUI dashboard, a *blocking* verification gate, a router that learns you, cost guardrails, team packs, cross-agent portability, and more. See **[docs/ROADMAP.md](docs/ROADMAP.md)**.

## License

MIT — see [LICENSE](LICENSE). Independent work; the tools it composes with belong to their respective authors, and are credited, not copied.

<div align="center"><sub>Built for people who want their agent to work like an engineer, not a slot machine.</sub></div>
