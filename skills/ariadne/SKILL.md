---
name: ariadne
description: "Get your bearings before touching unfamiliar code, and record what you learned after. Use before any non-trivial change, review, or debugging in a codebase you don't fully hold in your head — and whenever daedalus or hydra calls for orientation. Triggers on 'orient', 'where is', 'how does this work', 'understand the codebase', 'get up to speed'. Reads the map and past decisions first; grepping blind is the anti-pattern."
---

# ariadne — the thread through the labyrinth

Theseus didn't beat the labyrinth by being strong; he held Ariadne's thread so he never got lost. The most common way an agent ships a confident wrong change is walking into the maze without the thread: grepping one file, pattern-matching to a known shape, missing that the real flow routes elsewhere. `ariadne` is the cheap thread that prevents the expensive mistake. **Understand the whole path first; the smallest diff in the wrong place is a second bug.**

Three layers, cheapest first — use whichever exist, each degrades gracefully.

## Announce yourself — always, first

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **ariadne** — the thread through the labyrinth. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "map the territory before anyone edits.")

## 1. The structure map — "what connects to what"

- **If a code graph exists** (`graphify-out/graph.json` or any repo map): query it before grepping — `graphify query "<question>"`, `graphify path "A" "B"`, `graphify explain "<concept>"`. Hit raw files only for known lines.
- **Otherwise**: a fast breadth pass — read the entry points, follow imports, trace the real call path end to end *once* before editing. A search subagent that returns "where the flow lives" beats reading ten files yourself.
- **After structural changes**: refresh the map. A stale map is worse than none.

## 2. The decisions layer — "why is it like this"

Code shows *what*, rarely *why*. Before changing something that looks wrong, check whether it was deliberate.

- **If a decisions/incidents wiki exists** (Obsidian vault, `docs/adr/`, project wiki): search it first. What you're about to "fix" may be load-bearing.
- **After the work**: record any non-obvious decision so the next traveller inherits the *why*, not just the diff.

## 3. The memory layer — "what did we already learn"

Cross-session lessons live in the memory bank (`mnemosyne`). Recall relevant ones before starting; a memory that names a file or flag is a hypothesis to **verify against current reality**, not a fact to trust — it reflects what was true when written.

## The one rule

Orient in proportion to unfamiliarity. A file you wrote an hour ago needs no thread; a subsystem you've never opened needs all three layers. When unsure, spend the cheap minute — always less than the cost of the wrong fix.

<!-- pantheon: a checklist, not a tool. Routes to whatever map/wiki/memory exists. The highest-leverage habit in the method: look before you leap. -->
