---
name: hydra
description: "Fix a genuinely difficult bug -- diagnose the root cause, then seal it with a test. Use when the user says 'this bug is nasty', 'can't figure out why', or it resists the obvious fix. Triggers: 'bug', 'regression', 'flaky'. NOT for building features (use daedalus) or trivial fixes."
---

# hydra — slay it, then cauterize

Cut off one of the Hydra's heads and two grow back — until Heracles seared each stump with a torch. That is exactly a hard bug: patch the symptom and it returns somewhere else; only a root-cause fix *sealed with a regression test* stays dead. A hard bug is a **diagnosis** problem, not a **planning** problem — so this does the opposite of `daedalus`: no upfront pipeline, because you can't plan a fix for a mechanism you haven't found.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **hydra** — slay it, then cauterize. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "find the root cause, reproduce, fix at the root, seal with a test.")

## The method

1. **Orient to the blast radius** — run `ariadne` on the symptom: map what calls and is called by the suspect area before reading line by line. Check whether this failure mode was hit and solved before.
2. **Diagnose to root cause, not symptom** — form competing hypotheses and gather evidence *for and against each*. Don't touch code until you can name the mechanism ("inbound path reuses the outbound clock"), not just the symptom ("timestamp looks wrong").
   - Bundled: `pantheon:systematic-debugging`. If the oh-my-claudecode engine is installed and it's nasty → its `tracer` agent (competing hypotheses, evidence tracking, next-probe).
3. **Reproduce before fixing** — get the bug failing under a check you control (a test, a script, an observed value against real state). A fix you can't watch go fail→pass is a guess wearing a diff.
4. **Fix at the root** — grep *every* caller of the function you're about to change. The smallest correct fix is usually one guard in the shared path, not N guards in each caller; patching only the reported path leaves every sibling caller a live head.
5. **Cauterize** — if it could silently regress, seal it: a regression test that reproduces the bug and now passes, confirmed by a reviewer or a fresh run. This is the torch. Skip only for an obvious one-off.

## The discipline (where hard bugs are won or lost)

- **The user's hands-on ground truth outranks your probes and logs.** If they say "I can see it happen" or hand you a hypothesis ("try X"), test *exactly that* before theorizing an alternative. Their diagnosis of their own system usually beats your inference.
- **Never declare "impossible / unrecoverable" from a test that could be confounded.** A broken probe (empty token, wrong element, unengaged path) yields a confident wrong "it can't be done." Reproduce on the real production path before concluding anything is a hard ceiling.
- **State confidence honestly.** A fast wrong "solved!" costs more than a slow "let me verify the mechanism first."

<!-- pantheon: router over diagnosis + verification tools. The value is the ORDER (orient → diagnose → reproduce → root-fix → cauterize) and the discipline, not new code. -->

## Receipt — file your footprint (skipped in quiet mode)

When the task completes (or you hand back), file ONE honest line via Bash:

`~/.claude/pantheon/bin/pantheon receipt add --skill hydra --note "<what was done or caught, one line>"`

Good notes are outcomes, not activity: "root-caused reap loop, sealed with regression test", "deleted 340 dead lines", "flagged auth bypass in review". If the command doesn't exist yet (first session after install), skip silently — bookkeeping must never block or delay the actual work.
