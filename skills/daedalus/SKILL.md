---
name: daedalus
description: "Build something in best form, once — the full quality-gated path from a vague idea to reviewer-approved code. Use when the user says 'build this right', 'ship it properly', 'once and for all', or wants a non-trivial feature done thoroughly rather than fast. Triggers on 'build', 'implement', 'create the feature', 'do this properly'. NOT for bugs (use hydra) or one-line changes (edit directly)."
---

# daedalus — the master craftsman

Daedalus built things that *held* — wings that flew, a labyrinth no one escaped. A feature done "once and for all" is not one big step; it is a sequence of **quality gates, each catching a different failure class**: unclear requirements → wrong architecture → broken implementation → unverified quality. Skip a gate and that failure ships. `daedalus` runs the gates in order.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **daedalus** — the master craftsman. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "run the quality gates: scope, plan, challenge, build, review.")

## The method (works with any tools)

1. **Orient** — run `ariadne` first: read the map and past decisions for the area. Building without orienting re-solves solved problems.
2. **Scope until unambiguous** — turn the vague idea into a spec with no open questions: what's built, what's explicitly out, what "done" means as a testable statement.
3. **Plan, then have the plan challenged** — draft an approach, then run it past an independent critical pass *before* writing code. A plan no one argued with is a guess with formatting.
4. **Execute** — implement against the spec. Independent parts in parallel; long runs in the background.
5. **Verify with a different lens than you built with** — a separate review pass (correctness, security, quality). Never self-approve in the same breath you authored.

The discipline is **separate passes**: understand ≠ plan ≠ build ≠ verify, and the reviewer is never the author. Everything else is tooling.

## Concrete wiring (use what's installed, fall back when not)

- **`oh-my-claudecode`**: the sharpest path is `deep-interview` (scope) → `ralplan` (Planner/Architect/Critic consensus) → `autopilot` (detects the consensus plan, then parallel execution → QA loop → 3-reviewer validation).
- **`superpowers`**: `brainstorming` (scope) → `writing-plans` (plan) → `subagent-driven-development` (build) → `verification-before-completion` (verify).
- **Neither**: do the five steps by hand — write the spec to a file, spawn a subagent to critique it, implement, then spawn a *fresh* subagent to review against the spec.

For huge or sprawling builds, decompose with `argus` first, then run each slice through these gates. Keep the diff as small as `lethe` allows — the craftsman's mark is *no wasted material*.

## When NOT to use

- A **bug** → `hydra`. You cannot spec what you don't yet understand.
- A **clear, bounded task** → just implement it (or one executor subagent). Wrapping a one-liner in this pipeline is ceremony, not quality.

<!-- pantheon: pure router over the method + whatever planning/execution tools are installed. The value is the gate ORDER, not new machinery. -->
