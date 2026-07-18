---
name: clio
description: "Show the pantheon ledger — what the disciplines did, caught, spent, and learned: discipline heatmap, spend sparkline, receipts feed, lessons count, store health. Use when the user asks 'pantheon dashboard', 'pantheon stats/status', 'what did you do today/this week', or wants to see the plugin's footprint. Read-only; no side effects."
---

# clio — the pantheon's ledger, rendered

Receipts, lessons, routes, and spend all land in one SQLite store. This skill renders them so the value of the plugin is visible instead of vibes.

## Announce yourself — first (skipped in economy/quiet mode)

> 🏛 **dashboard** — the ledger, rendered. **Task:** show what pantheon did and spent. **Plan:** run the dashboard read-only, summarize the two most notable numbers.

## How to run it

1. Via Bash: `~/.claude/pantheon/bin/pantheon dashboard --plain`
   Fallback if the shim doesn't exist yet (first session): `python3 ~/.claude/plugins/marketplaces/pantheon/scripts/dashboard.py --plain`
2. Show the output verbatim in a code block (it is already formatted), then add a 1–2 line human summary: the busiest discipline, notable spend, anything unhealthy.
3. If the user wants it LIVE, tell them to run `~/.claude/pantheon/bin/pantheon dashboard` in their own terminal — full-screen TUI, refreshes every 2s, `q` quits.

## Notes

- Empty dashboard = the store is new; receipts accrue as disciplines run.
- `db ✗ CORRUPT` in the health line → run `pantheon doctor` (v1.0+) or delete `~/.claude/pantheon/pantheon.db` (it self-recreates; lessons are lost).
- This skill never writes anything.
