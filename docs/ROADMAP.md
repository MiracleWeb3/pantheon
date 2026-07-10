# pantheon roadmap — v0.7 → v1.1

> **Status: ALL 12 FEATURES SHIPPED** (v0.8 → v1.1, July 2026). Kept as the design record — what each feature does and why they layer in this order.

The 12 features that make pantheon the only agent plugin worth keeping. Phased by moat-per-effort and dependency. Design decision: **max power** — a local SQLite store backs memory, receipts, metrics, and routing feedback, so features compound on one substrate instead of a dozen JSON files.

## Foundation — the store (lands with Phase 1)

`~/.claude/pantheon/pantheon.db` (SQLite, stdlib `sqlite3`, WAL mode, created on demand, migrations versioned). One substrate, five tables:

| Table | Holds | Feeds |
|---|---|---|
| `lessons` | captured memory: text, tags, file/topic keys, embedding-lite keywords, weight | #1 retrieval, #2 routing |
| `receipts` | per-discipline action log: skill, task, what it did/caught, tokens, ts | #3 receipts, #4 dashboard, #12 doctor |
| `routes` | router fires + accepted/overridden outcome | #2 adaptive routing |
| `metrics` | rollups: spend, disciplines used, lines±, regressions caught | #4 dashboard, #5 budget |
| `meta` | schema version, config cache, migration state | #12 migrate |

Fail-safe rule unchanged: any hook that touches the DB wraps in try/except and exits 0 — a corrupt DB never breaks a session. A `--selftest` on every module.

---

## Phase 1 — v0.8 "It remembers, it proves itself" (the moat four) ✅ shipped

**#1 Retrieval-augmented memory.** `mnemosyne` already captures; add *auto-recall*. A UserPromptSubmit hook keyword-matches the prompt + touched files against `lessons` and injects the top 1–3 relevant ones as context (`[PANTHEON RECALL] Last time near this: …`). Scored by keyword overlap × recency × weight. This is the headline feature — memory that surfaces itself.

**#3 Receipts.** Each discipline, on completion, writes a one-line `receipts` row. Surfaced in the dashboard and as an optional end-of-session summary: *"this session: hydra fixed 2 root causes, lethe −340 lines, themis flagged 1 security issue."*

**#6 Blocking verification gate.** A Stop hook that inspects the turn's changed files + last test run and **blocks completion** (non-zero / `decision: block`) when: tests failed, `TODO`/`FIXME`/`test.skip`/placeholder stubs were introduced, or a product-code change shipped with no verification run. Config-gated (off in `quiet`, warn-only in `economy`). OMC only advises this — pantheon enforces it.

**#4 `/pantheon dashboard`.** A TUI (max-power: full-screen `curses`, falls back to plain print) reading the DB: discipline-usage heatmap, 7-day spend sparkline, lessons count, receipts feed, active config, hook health.

*Acceptance: recall injects a real past lesson on a repeat topic; a failing test blocks "done"; dashboard renders live DB data; receipts accrue. All hooks fail-silent + selftest.*

## Phase 2 — v0.9 "It learns you" ✅ shipped

**#2 Adaptive routing.** Router logs each fire to `routes`; a lightweight follow-up records whether the routed skill was actually used or overridden. Weights per (phrase-cluster → skill) adjust, so routing personalizes. Ships with a decay so stale patterns fade.

**#8 Auto intent-clarifier.** On a prompt that is both *vague* (no file/function/spec anchor) and *large* (build/refactor scope), auto-fire a 2–3 question `deep-interview` before any work — kills wrong-thing-built waste.

**#7 Proactive context management.** The HUD already computes context fill. Add a discipline + hook that at ≥85% offers/does a checkpoint: summarize the plan + open threads into `alexandria`/`lessons`, so a `/clear` loses nothing. Nobody handles the context wall gracefully today.

## Phase 3 — v1.0 "It won't surprise you" ✅ shipped

**#5 Cost guardrails.** `budget` config (`session`, `daily`, `weekly` USD). HUD turns red near cap; a hook warns at 80% and can hard-pause at 100% (`ask`/`warn`/`block` modes). Reads the same ledger the HUD already keeps.

**#12 `/pantheon doctor` + auto-migrate.** Checks hook wiring, config validity, DB integrity, broken/duplicate skills, stale caches — and fixes what it can. SessionStart auto-migrates config + DB schema across versions silently.

## Phase 4 — v1.1 "It spreads" ✅ shipped

**#9 Team packs.** `pantheon.pack.json` committed to a repo: disciplines on/off, shared lessons, standards, budget. On entering the repo, pantheon merges the pack (project > pack > user). A new hire inherits the team's accumulated wisdom on install — the real lock-in.

**#10 Discipline authoring + sharing.** `/pantheon forge <name>` scaffolds a discipline (SKILL.md + announce block + optional route pattern + provenance). A share/import format so the community grows the pantheon without the maintainer.

**#11 Cross-agent portability.** Skills are Markdown; package a build that also loads in Codex / Cursor / other agents (adapters for each host's skill/hook conventions). "Install once, works in every agent" — a claim no rival makes.

---

## Sequencing rationale

- **Phase 1 first** because it's the pitch (remember · prove · see · enforce) and it lays the DB every later phase reuses.
- **Phase 2** turns the static router into a learning one — needs Phase 1's `routes`/`lessons`.
- **Phase 3** is reliability + control; low risk, high trust.
- **Phase 4** is network effects — highest moat but only worth it once the single-user product is undeniable.

Each phase is one spec → plan → implement → verify cycle, shipped as its own version. Nothing here breaks the current zero-dependency install except the SQLite store, which is Python-stdlib (`sqlite3`) — still no pip, no npm.
