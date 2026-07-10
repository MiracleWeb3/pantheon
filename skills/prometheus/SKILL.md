---
name: prometheus
description: "Write the test before the code — red/green/refactor TDD. Use when starting a well-specified unit of logic, when the user says 'test first', 'tdd', 'write the test', or when a contract is clear enough to pin with a test before implementing. Triggers on 'tdd', 'test-driven', 'test first', 'red green refactor', 'write a failing test'. NOT for exploratory spikes where the shape is still unknown."
---

# prometheus — foresight

Prometheus means *forethought*: he saw what was coming before it arrived. The test written **before** the code is exactly that — it pins the contract before the implementation exists to cheat against it. A test written after the fact tends to assert whatever the code happens to do; a test written first asserts what the code *should* do.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **prometheus** — foresight. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "pin the contract with a failing test before the code.")

## The cycle

1. **Red** — write a test that states the requirement, and **watch it fail**. A test that passes before you've written the code is testing nothing — that failing run is proof the test can detect the behavior's absence.
2. **Green** — write the *least* code that makes it pass. Not the elegant version, not the general version — the one that turns the bar green. (`lethe` lives here.)
3. **Refactor** — now clean it up with the test as your safety net: dedupe, rename, simplify. The green bar tells you nothing broke.

Repeat one small behavior at a time.

## Concrete wiring

- **Bundled** → `pantheon:test-driven-development` / `pantheon:tdd` for the full discipline.
- **Otherwise** → do the loop by hand: write the failing test in the project's existing framework, run it, see red, implement, see green, refactor.

## When it fits (and when it doesn't)

- **Fits**: a clear contract — a parser, a calculation, a state transition, a money/security path. Anywhere the "what" is known and only the "how" is open.
- **Doesn't**: an exploratory spike where you don't yet know the shape. Explore first, *then* pin it with tests. Forcing TDD onto an unknown design tests your guesses, not the requirement.

Complements the others: `hydra` cauterizes a bug with a regression test *after* diagnosis; `prometheus` writes the test *before* the code. `lethe`'s "leave one runnable check" is the floor; `prometheus` is the full discipline for logic that warrants it.

<!-- pantheon: red→green→refactor. Routes to the tdd skill or the hand loop. The value is check-FIRST, so the contract is pinned before the code can drift. -->

## Receipt — file your footprint (skipped in quiet mode)

When the task completes (or you hand back), file ONE honest line via Bash:

`~/.claude/pantheon/bin/pantheon receipt add --skill prometheus --note "<what was done or caught, one line>"`

Good notes are outcomes, not activity: "root-caused reap loop, sealed with regression test", "deleted 340 dead lines", "flagged auth bypass in review". If the command doesn't exist yet (first session after install), skip silently — bookkeeping must never block or delay the actual work.
