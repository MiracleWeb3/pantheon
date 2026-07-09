---
name: themis
description: "Review code with an independent, adversarial eye — correctness, security, and quality — as a pass separate from whoever wrote it. Use when the user says 'review this', 'is this correct', 'check my code', 'audit', or before merging non-trivial changes. Triggers on 'review', 'audit', 'is this right', 'find bugs', 'before I merge', 'code review'. The reviewer is never the author."
---

# themis — weigh it fairly

Themis holds the scales of divine order and weighs without favor. Review is the pass that catches what building missed — and **the author is the worst judge of their own work**, because they review the code they *meant* to write, not the code on the page. So `themis` runs as a distinct pass, ideally by a fresh context, never self-approved in the same breath the code was authored.

## Announce yourself — always, first

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **themis** — the scales of judgment. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "weigh the change adversarially: correctness, security, quality.")

## What to weigh — three scales

1. **Correctness** — does it do what it claims, and what happens at the edges? Empty input, nulls, concurrency, off-by-one, the error path, the case the happy path ignored. Trace the actual logic; don't pattern-match "looks fine."
2. **Security** — trust boundaries validated, no secrets in code or logs, injection/traversal/SSRF where untrusted input flows, authz on the real path. (For a deep pass, route to a dedicated security lens.)
3. **Quality** — clarity over cleverness, duplication that should be shared, a simpler path missed (`lethe`), naming that lies, comments that state *why* not *what*.

## The discipline

- **Adversarial, not confirmatory.** Try to *break* the change, not to bless it. "What input makes this wrong?"
- **Rank by severity**, most-dangerous first — a crash-on-empty beats a style nit.
- **Verify each finding before reporting it.** A confident wrong review finding costs trust; confirm the failure is real (the input, the state, the line) before you raise it. Don't cry wolf.
- **Concrete over vague** — "fails when `items` is empty at line 42" beats "add error handling."

## Concrete wiring

- **`oh-my-claudecode`** → `code-reviewer` (severity-rated), `critic` (thorough multi-perspective), `security-reviewer` (OWASP/secrets).
- **`superpowers`** → `requesting-code-review` / `receiving-code-review`.
- **The `code-review` skill** if present, or a fresh subagent handed the diff and told to find what's wrong.

Pairs as the gate after `daedalus`/`hydra` and before `charon` — nothing gets ferried across until it's been weighed.

<!-- pantheon: the missing half of "separate your passes". Routes to review agents; the discipline is adversarial, severity-ranked, self-verified, reviewer≠author. -->
