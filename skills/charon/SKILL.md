---
name: charon
description: "Land finished work: clean atomic commits, a well-formed PR, and finish-the-branch hygiene. Use when the user says 'commit this', 'open a PR', 'land it', 'ship it', 'finish the branch', after a change is built and reviewed. Triggers on 'commit', 'PR', 'pull request', 'land', 'merge', 'push', 'finish the branch'. Only commits/pushes when asked."
---

# charon — ferry it across

Charon carries souls across the river to the other side; without the ferryman they wait on the near bank forever. Work is the same: written and reviewed but uncommitted, it hasn't crossed — it isn't real to anyone else yet. `charon` turns finished work into a merged, reviewable artifact.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **charon** — the ferryman. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "land the work: atomic commits, a clean PR, nothing shipped unasked.")

## The crossing

1. **Atomic commits** — one logical change per commit, in an order that tells a story. Not one giant "wip" blob; not fifty micro-commits. The message says **why**, not just what — the diff already shows the what.
2. **Branch hygiene** — branch off the main branch *first* if you're on it (never commit straight to main unless told). Rebase/tidy so history is clean, no stray debug files, no unrelated changes swept in.
3. **A well-formed PR** — title states the change; body says what, why, and **how to verify**. Link the issue. A reviewer should understand it without archaeology.
4. **Green before crossing** — tests/build/lint pass, and a **secrets scan** before push (no tokens, keys, or `.env` content in the diff — this is a trust boundary; `lethe` never skips it).

## The rules

- **Never commit or push unless the user asked.** Landing is outward-facing and hard to reverse; approval to build is not approval to ship.
- **End commit messages** with any co-author trailer the project convention uses.
- **PR body**: state how it was verified (the actual command/output), not "should work."

## Concrete wiring

- **`oh-my-claudecode`** → `git-master` (atomic commits, style detection, rebasing).
- **`superpowers`** → `finishing-a-development-branch`.
- **Otherwise** → group the diff into logical commits by hand, write real messages, and `gh pr create` with a proper body.

The last mile after `themis` approves — foresight (`prometheus`), build (`daedalus`), review (`themis`), then the ferry across.

<!-- pantheon: the finish line. Routes to git tooling; the discipline is atomic commits, why-not-what messages, secrets-scan, and never-ship-unasked. -->

## Receipt — file your footprint (skipped in quiet mode)

When the task completes (or you hand back), file ONE honest line via Bash:

`~/.claude/pantheon/bin/pantheon receipt add --skill charon --note "<what was done or caught, one line>"`

Good notes are outcomes, not activity: "root-caused reap loop, sealed with regression test", "deleted 340 dead lines", "flagged auth bypass in review". If the command doesn't exist yet (first session after install), skip silently — bookkeeping must never block or delay the actual work.
