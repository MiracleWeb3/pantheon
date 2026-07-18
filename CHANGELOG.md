# Changelog

All notable changes. Versions follow semver; the manifest (`.claude-plugin/plugin.json`) is the source of truth.

## 3.0.0 — 2026-07-19

The subtraction release: pantheon stops doing memory.

- **Breaking — all memory features removed.** Gone: the `lessons` table and BM25 recall, the Stop-hook learning capture and its inbox, per-prompt recall injection, the `recall` config knob, the `pantheon lesson` and `pantheon recall` CLI verbs, the `pantheon_recall` / `pantheon_lesson_add` MCP tools, and the `mnemosyne` / `alexandria` / `anamnesis` / `stele` disciplines. 188 skills → 184.
- **Why** — [claude-memory-light](https://github.com/MiracleWeb3/claude-memory-light) indexes every Claude Code transcript verbatim into SQLite FTS5 for zero tokens, and answers "what did we decide about X" better than a curated lesson table ever did. Running both meant two half-memories competing, one of them a lossy summary of what the other already had complete. A plugin should not ship a worse copy of a job something else does properly.
- **Kept and sharpened** — the verification gate, the adaptive router, receipts, the dashboard, doctor, budget caps, forge, team packs (config + standards, no lessons now).
- **Upgrade is lossless.** Databases created before 3.0 keep their `lessons` table as an orphan: never read, never pruned, never dropped. Nothing captured is destroyed; `sqlite3 ~/.claude/pantheon/pantheon.db 'SELECT text FROM lessons'` still reads it.
- **Gate fix (also in 2.0.1)** — the block budget was keyed on a hash of the prompt text, so typing "continue" twice inside 2h let the second turn inherit the first's exhausted counter and the gate silently never fired. Now keyed on the payload's `prompt_id`, with `stop_hook_active` as a floor.

## 2.0.0 — 2026-07-18

The naming release: every discipline carries its own name now, so nothing routes on ordinary English.

- **Breaking — 21 disciplines renamed.** `dashboard`→`clio`, `doctor`→`asclepius`, `forge`→`hephaestus`, `forge-session`→`hephaestus-session`, `oracle`→`sibyl`, `ask`→`socrates`, `brag`→`kleos`, `budge`→`metron`, `cancel`→`atropos`, `debug`→`theseus`, `learner`→`mathesis`, `plan`→`boule`, `prototype`→`pygmalion`, `release`→`hermes`, `remember`→`anamnesis`, `skill`→`techne`, `team`→`argonauts`, `trace`→`ichnos`, `triage`→`krisis`, `verify`→`basanos`, `wiki`→`stele`.
- **Why** — a discipline named after a common word gets matched on that word. "my postgres oracle migration is failing" summoned the read-the-docs discipline; "the forge is hot" summoned the skill author; a bug report that happened to say "dashboard chat" put the telemetry ledger on top of the debugging disciplines. Once junk lands on top you stop reading the suggestions at all, which is the exact failure the routing exists to prevent.
- **Technology names kept** — `vitest`, `shadcn`, `threejs-*`, `vite`, `pnpm`. The name is the search term; nothing is improved by being called something in Greek.
- **No discoverability cost** — routing reads descriptions as well as names, so every renamed discipline still comes back from a plain sentence about what it does. Checked one by one: "cancel the running mode" finds `atropos`, "guide me through cutting a release" finds `hermes`, "verify this really works before i claim its done" finds `basanos`.

**Migration:** replace `/pantheon:<old>` with `/pantheon:<new>` from the list above. Nothing else changed.

## 1.4.0 — 2026-07-10

The hardening release: a four-agent adversarial audit (core code, competitive gaps, skills integration, claim-vs-reality), every critical/high finding closed.

- **Security** — team-pack lessons are clamped (weight 0.5–2.0, text ≤300 chars), scoped to the repo that shipped them, and never recalled outside it; pack "standards" inject as repo conventions that never override the user; `pack init` excludes auto-captured lessons (secret-safety) unless `--include-captured`.
- **Gate** — fails OPEN if its block counter can't persist (an unwritable state dir can no longer wedge a session); missing-verification nudges block once, hard failures (failing checks, stubs) still twice; large deletions now count as unverified churn.
- **Memory** — auto-lessons require a STRONG correction signal (a stray "no"/"not"/"again" stays in the inbox); auto-lessons need ≥2 shared keywords to resurface; project inboxes are bounded (256KB → 64KB tail) and auto-gitignored.
- **Durability** — every JSON state write is atomic (tmp+rename); the spend ledger survives concurrent sessions (merge-on-write baselines, atomic prune, timestamped session entries that age out); SQLite `busy_timeout` 3s and a schema fast-path (no write transaction per prompt).
- **Adaptive routing actually resolves** — outcomes are read from the store per session; a second routed prompt no longer clobbers the first's pending resolution (superseded fires count as `ignored`), so route demotion can finally trigger.
- **Router** — `the design` / `too much` overfires removed; custom-route regexes length-capped and matched against a bounded haystack (catastrophic backtracking can't eat the hook budget).
- **Store** — monthly retention sweep (routes/metrics 90d, receipts 180d, never-recalled auto-lessons 90d) wired into SessionStart and `doctor --fix`.
- **Doctor** — transcript-format drift tripwire (a Claude Code format change can't silently blind the gate/receipts/meters); reports store size, prune age, and the measured per-session token cost of skill listings.
- **HUD** — transcript discovery walk memoized (120s TTL); all cache writes atomic.
- **CI** — ubuntu/macos/windows × Python 3.9/3.13 matrix.
- **Docs** — version coherence (badge == manifest == changelog), license claims now match CREDITS reality, renamed-skills claim scoped to what is actually renamed.

## 1.3.0 — 2026-07-10

- HUD subscription meters: exact 5-hour-window and weekly used-% from Claude Code ≥2.1 `rate_limits`; transcript-derived `≈` fallback (self-calibrating) on older versions; `⌁api` tag for API-key sessions.

## 1.2.1 — 2026-07-10

- Gate hardening: per-session block counters (no cross-session clobber), stale-counter expiry, machine-generated "user" entries excluded from turn scans, a failing build counts as a failing check.
- Receipts: token counts deduped by message id (no more 2–5× inflation); one bad ledger line can't blind the budget.

## 1.2.0 — 2026-07-10

- Pantheon-native names for the flagship merged sets — `spartan` (lazy-dev), `sisyphus`/`automedon`/`hekaton`/`pythia` (engine power modes) — with the full old→new map in CREDITS.md.

## 1.1.0 — 2026-07-10

- Team packs (committed config + lessons), `forge` (author custom disciplines), cross-agent export (cursor / codex / generic).

## 1.0.0 — 2026-07-09

- Budget guardrails (session/daily/weekly USD caps; warn/ask/block) and `pantheon doctor`.

## 0.9.0 — 2026-07-09

- Adaptive routing (ignored routes demote themselves), intent clarifier, context-wall guard.

## 0.8.0 — 2026-07-09

- The moat four: SQLite store, self-recalling memory, receipts + TUI dashboard, and a verification gate that actually blocks.

## 0.7.0 and earlier — 2026-07-09

- 0.7: the HUD (effort, session time, live context %, hourly/weekly spend). 0.6: the merge — superpowers, oh-my-claudecode, ponytail, ui-skills, attributed. 0.5: presets + three disciplines. 0.4: auto-routing + self-announce. 0.2–0.3: the mythic lifecycle. 0.1: born as "modus".
