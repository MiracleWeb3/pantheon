---
name: oracle
description: "Consult real documentation before using an unfamiliar SDK, API, or library -- never code from memory. Use before writing code you don't use daily, when the user says 'how do I use X', or a call keeps failing like a wrong signature. Triggers: 'docs', 'API', 'SDK', 'latest version'."
---

# oracle — consult before you act

No Greek hero moved on a hard question without consulting the oracle first. The single most common way an agent ships broken code is calling an API from memory — a signature that changed, an option that never existed, a pattern from a different version. `oracle` is the cheap consultation that prevents the confident-wrong call.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **oracle** — consult before you act. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "verify the external contract against real docs.")

## The rule

**Never answer SDK/API usage from memory. Verify against current docs.** Your training has a cutoff; libraries move. A five-minute doc check beats an hour debugging a call that was never valid.

## The method

1. **Repo docs first** — the project's own README, `docs/`, examples, and existing usage of the same library. How *this* codebase already calls it is the most authoritative source.
2. **Official docs next** — the library's real documentation for the version in `package.json` / `requirements.txt` / lockfile. Version matters; check which one is installed.
3. **Ground the claim** — cite the doc you actually read, not a memory that feels right. If you couldn't verify, say so and mark the risk.

## Concrete wiring (use what's installed)

- **`oh-my-claudecode`** → the `document-specialist` agent (repo docs → Context Hub / `chub` → graceful web fallback).
- **A docs MCP** (context7, etc.) → query it for the exact version's API.
- **Otherwise** → `WebFetch` the official docs page, or read the library source in `node_modules` / site-packages directly.

## When NOT to use

Something you genuinely use every day and the code confirms the shape. Don't ceremonially "research" `console.log`. But the moment a call is non-obvious or version-sensitive, consult — `lethe` never applies to skipping verification of an external contract.

Pairs with `daedalus`: when a build touches unfamiliar tech, `oracle` runs inside the scope step so the plan is grounded in how the API actually works.

<!-- pantheon: prevents the #1 agent failure — confidently misusing an API. Routes to doc tools; the discipline is "verify the external contract, never recall it." -->

## Receipt — file your footprint (skipped in quiet mode)

When the task completes (or you hand back), file ONE honest line via Bash:

`~/.claude/pantheon/bin/pantheon receipt add --skill oracle --note "<what was done or caught, one line>"`

Good notes are outcomes, not activity: "root-caused reap loop, sealed with regression test", "deleted 340 dead lines", "flagged auth bypass in review". If the command doesn't exist yet (first session after install), skip silently — bookkeeping must never block or delay the actual work.
