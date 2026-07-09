---
name: ship
description: "Build something in best form, once — the full quality-gated path from a vague idea to reviewer-approved code. Use when the user says '/ship', 'ship it properly', 'build this right', 'once and for all', or wants a non-trivial feature done thoroughly rather than fast. NOT for bugs (use modus:hardbug) or one-line changes (edit directly)."
---

# ship — build it right, once

A feature done "once and for all" is not one big step; it is a sequence of **quality gates, each catching a different failure class**: unclear requirements → wrong architecture → broken implementation → unverified quality. Skip a gate and that failure ships. `ship` runs the gates in order.

## The method (works with any tools)

1. **Orient** — before touching code, run the `modus:orient` skill: read the map of the area and any past decisions about it. Building without orienting is how you re-solve solved problems.
2. **Scope until unambiguous** — turn the vague idea into a spec with no open questions. What exactly is being built, what's explicitly out, what does "done" mean as a testable statement.
3. **Plan, then have the plan challenged** — draft an approach, then run it past an independent critical pass *before* writing code. A plan no one argued with is a guess with formatting.
4. **Execute** — implement against the spec. Independent parts in parallel; long runs in the background.
5. **Verify with a different lens than you built with** — a separate review pass (correctness, security, quality). Never self-approve in the same breath you authored.

The discipline is **separate passes**: understand ≠ plan ≠ build ≠ verify, and the reviewer is never the author. Everything else is tooling.

## Concrete wiring (use what's installed)

- **If `oh-my-claudecode` is installed** — the sharpest path is its 3-stage pipeline: `Skill("oh-my-claudecode:deep-interview")` (scope) → `Skill("oh-my-claudecode:ralplan")` (Planner/Architect/Critic consensus) → `Skill("oh-my-claudecode:autopilot")` (it detects the consensus plan, then runs parallel execution → QA loop → 3-reviewer validation). This is steps 2→5 with real gates.
- **If `superpowers` is installed** — `Skill("superpowers:brainstorming")` (scope) → `Skill("superpowers:writing-plans")` (plan) → `Skill("superpowers:subagent-driven-development")` or `executing-plans` (build) → `Skill("superpowers:verification-before-completion")` (verify).
- **Neither** — do the five steps by hand: write the spec to a file, spawn one subagent to critique it, implement, then spawn a *fresh* subagent to review against the spec.

## When NOT to use

- A **bug** → `modus:hardbug`. You cannot spec what you do not yet understand.
- A **clear, bounded task** → just implement it (or one executor subagent). Wrapping a one-liner in this pipeline is ceremony, not quality.

<!-- modus: pure router over the method + whatever planning/execution tools are installed. The value is the gate ORDER, not new machinery. -->
