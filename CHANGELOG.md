# Changelog

All notable changes. Versions follow semver; the manifest (`.claude-plugin/plugin.json`) is the source of truth.

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
