---
name: doctor
description: "Diagnose and repair the pantheon install: hooks wiring, module selftests, config validity, SQLite store integrity (rebuild with backup), spend-ledger health, CLI shim, duplicate skills. Use when the user says 'pantheon is broken/not working', 'fix pantheon', 'pantheon doctor', routing/recall/gate stopped working, or after a version update that behaves oddly."
---

# doctor — heal the pantheon

Every moving part of the plugin gets a check, and the safe repairs apply themselves. Nothing destructive happens without `--fix`, and even `--fix` backs up before it rebuilds.

## Announce yourself — first (skipped in economy/quiet mode)

> 🏛 **doctor** — heal the pantheon. **Task:** diagnose the install. **Plan:** run the checks read-only, report, then fix what the user approves.

## How to run it

1. Diagnose (read-only): `~/.claude/pantheon/bin/pantheon doctor`
   Fallback if the shim is missing: `python3 ~/.claude/plugins/marketplaces/pantheon/scripts/doctor.py`
2. Show the check list verbatim. `✓` healthy · `⚠` warning · `✗` failing.
3. If anything is ✗/⚠ and marked fixable, ask the user (one line), then run with `--fix`. The store rebuild renames the corrupt DB to `pantheon.db.corrupt-<ts>` — it is never deleted, say so.
4. Re-run without `--fix` to confirm the tree is healthy, and report before/after in one line.

## What it cannot fix

- Duplicate skill names among the 170+ merged skills — report them; pruning is the user's call.
- A stale plugin version — that's `claude plugin update pantheon@pantheon` + restart.
- Hooks not loading at all (this skill can't run then either): `claude plugin details pantheon@pantheon` should show Hooks; if not, reinstall.
