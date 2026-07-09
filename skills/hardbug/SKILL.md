---
name: hardbug
description: "Fix a genuinely difficult bug — diagnose the root cause first, then optionally lock the fix with a regression test. Use when the user says '/hardbug', 'this bug is nasty', 'can't figure out why', a bug resists the obvious fix, or a regression keeps returning. NOT for building features (use modus:ship) or trivial fixes (edit directly)."
---

# hardbug — root cause, then lock it

A hard bug is a **diagnosis** problem, not a **planning** problem. So this does the opposite of `modus:ship`: no upfront pipeline, because you cannot plan a fix for a mechanism you have not found yet. Understand first, fix second, lock third.

## The method

1. **Orient to the blast radius** — run `modus:orient` on the symptom: map what calls and is called by the suspect area before reading line by line. Check whether this failure mode was hit and solved before.
2. **Diagnose to root cause, not symptom** — form competing hypotheses and gather evidence *for and against each*. Do not touch code until you can name the mechanism ("inbound path reuses the outbound clock"), not just the symptom ("timestamp looks wrong").
   - If `superpowers` is installed: `Skill("superpowers:systematic-debugging")`.
   - If `oh-my-claudecode` is installed and it's nasty: its **tracer** agent is purpose-built — `Task(subagent_type="oh-my-claudecode:tracer", ...)` — competing hypotheses, evidence tracking, next-probe recommendation.
3. **Reproduce before fixing** — get the bug failing under a check you control (a test, a script, an observed value against real state). A fix you cannot watch go fail→pass is a guess wearing a diff.
4. **Fix at the root** — grep *every* caller of the function you're about to change. The smallest correct fix is usually one guard in the shared path, not N guards in each caller; patching only the reported path leaves every sibling caller still broken.
5. **Lock it — only if it could silently regress** — wrap the fix so a reviewer confirms *"a test reproducing the bug now passes"* before it's called done (`oh-my-claudecode:ralph` does this as a loop; or just write the regression test and run it). Skip for an obvious one-off.

## The discipline (this is where hard bugs are won or lost)

- **The user's hands-on ground truth outranks your probes and logs.** If they say "I can see it happen" or hand you a hypothesis ("try X"), test *exactly that* before theorizing an alternative. Their diagnosis of their own system usually beats your inference.
- **Never declare "impossible / unrecoverable" from a test that could be confounded.** A broken probe (empty token, wrong element, unengaged path) yields a confident wrong "it can't be done." Reproduce on the real production path before concluding anything is a hard ceiling.
- **State confidence honestly.** A fast wrong "solved!" costs more than a slow "let me verify the mechanism first."

<!-- modus: router over diagnosis + verification tools; the value is the ORDER (orient → diagnose → reproduce → root-fix → lock) and the discipline, not new code. -->
