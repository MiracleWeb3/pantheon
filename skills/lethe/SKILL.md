---
name: lethe
description: "Reach for the simplest solution that actually works — YAGNI, standard library before custom code, native platform features before dependencies, one line before fifty, deletion before addition. Use when writing, refactoring, reviewing, or choosing libraries, and when the user says 'simplest', 'minimal', 'do less', 'yagni', 'lazy', or complains about over-engineering, bloat, or boilerplate. NOT for non-coding requests."
---

# lethe — the river of forgetting

The dead drank from Lethe and let go of everything they no longer needed. The best code obeys the same instinct: **the code you never write is the code you never debug at 3am.** Lazy here means *efficient, not careless* — a senior engineer who has been paged for every over-built system and forgets, on purpose, everything the task doesn't truly need.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **lethe** — the river of forgetting. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "find the simplest form that still works.")

## The ladder — stop at the first rung that holds

1. **Does this need to exist at all?** Speculative need = skip it, say so in one line. (YAGNI)
2. **Already in this codebase?** A helper, util, type, or pattern a few files over → reuse it. Re-implementing what already exists is the most common slop.
3. **Standard library does it?** Use it.
4. **Native platform feature covers it?** `<input type="date">` over a picker lib, CSS over JS, a DB constraint over app code.
5. **An already-installed dependency solves it?** Use it. Never add a new dependency for what a few lines can do.
6. **Can it be one line?** One line.
7. **Only then**: the minimum code that works.

The ladder runs *after* you understand the problem, not instead of it. Trace the real flow first (`ariadne`), then climb. Two rungs work → take the higher one and move on.

## Rules

- **Bug fix = root cause, not symptom.** One guard in the shared function beats a guard in every caller — a smaller diff *and* it fixes the siblings the ticket didn't name. (This is why `hydra` greps every caller.)
- No unrequested abstractions: no interface with one implementation, no factory for one product, no config for a value that never changes.
- **Deletion over addition.** Boring over clever — clever is what someone decodes at 3am.
- Mark a deliberate shortcut with its ceiling: `# lethe: global lock, per-account if throughput matters`. Intent, not ignorance.

## When NOT to be lazy

Never simplify away input validation at trust boundaries, error handling that prevents data loss, security, accessibility basics, or anything explicitly requested. Never lazy about *understanding* — the ladder shortens the solution, never the reading. A tiny diff in the wrong place isn't lazy, it's a second bug. And leave the calibration knob real hardware needs; the physical world has drift a minimal model can't see.

## Leave one check

Non-trivial logic (a branch, a loop, a parser, a money/security path) leaves ONE runnable check behind — the smallest thing that fails if the logic breaks. No frameworks, no fixtures unless asked. Trivial one-liners need none; YAGNI applies to tests too.

<!-- pantheon: the economy discipline — original, in the spirit of "lazy senior dev" minimalism. Pairs with every other skill: orient fully, then build/fix the least that works. -->

## Receipt — file your footprint (skipped in quiet mode)

When the task completes (or you hand back), file ONE honest line via Bash:

`~/.claude/pantheon/bin/pantheon receipt add --skill lethe --note "<what was done or caught, one line>"`

Good notes are outcomes, not activity: "root-caused reap loop, sealed with regression test", "deleted 340 dead lines", "flagged auth bypass in review". If the command doesn't exist yet (first session after install), skip silently — bookkeeping must never block or delay the actual work.
