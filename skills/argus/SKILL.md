---
name: argus
description: "Take on a task too big for one context — a huge input, a sprawling migration, a broad audit, a hard multi-part problem — by decomposing it and fanning out parallel subagents, one per slice, then synthesizing. Use when the user says 'this is huge', 'too big', 'do it across the whole repo', 'rlmit', or an input won't fit in context. Triggers on 'huge', 'massive', 'entire codebase', 'all files', 'migrate everything', 'decompose', 'in parallel'. NOT for a single focused task (just do it)."
---

# argus — the hundred eyes

Argus Panoptes had a hundred eyes and watched everything at once; some slept while others kept watch. That is how you take on work no single context can hold: split it into slices and give each a fresh pair of eyes running in parallel. Trade tokens for quality *on purpose* here — this is not the default for small tasks.

## The method

1. **Offload — don't inhale the whole thing.** Keep big inputs on disk; probe by metadata first (size, structure, head, counts). Reading a 200-file corpus into one context blinds you; measure it, then slice it.
2. **Decompose** — cut the work along a natural seam: script-chunk a large input, split a migration by file or module, break a hard problem into independent sub-questions. Each slice must be answerable on its own.
3. **Recurse — one clean context per slice.** Spawn one subagent per slice, each with a *fresh* context and a narrow prompt, each returning a small structured result. Clean context per slice is the whole point: no cross-contamination, no lost-in-the-middle. For large fan-outs, prefer a deterministic Workflow (pipeline/parallel) over hand-spawning.
4. **Synthesize** — merge the structured results into the answer, and **verify before finalizing**. The merge is where a missed slice or a contradiction surfaces; a completeness pass ("what modality/file/claim did we not cover?") catches the tail.

## Parallelism discipline

- Independent slices fire **simultaneously** — never serialize independent work. Long operations (installs, builds, test suites) go to the background so other slices proceed.
- Match the fan-out to the task: a few slices for "audit these modules", dozens for "migrate every call site". If you bound coverage (top-N, sampling, no-retry), **say so** — silent truncation reads as "covered everything" when it didn't.
- Route each slice to the right tier: cheap mechanical slices to a fast model, hard reasoning slices to a strong one.

## When NOT to use

A single focused change, or anything that fits comfortably in one context. Fanning out a small task just adds coordination overhead — `lethe` says do it directly.

<!-- modus: this is the RLM / divide-and-conquer discipline. The value is offload → decompose → clean-context recurse → verified synthesis, applied only when scale actually demands it. -->
