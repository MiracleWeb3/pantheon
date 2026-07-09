---
name: orient
description: "Get your bearings before touching unfamiliar code, and record what you learned after. Use before any non-trivial change, review, or debugging in a codebase you don't fully hold in your head — and whenever modus:ship or modus:hardbug calls for orientation. Reads the map and past decisions first; grepping blind is the anti-pattern."
---

# orient — read the map before you walk

The most common way an agent ships a confident wrong change is acting before understanding: grepping one file, pattern-matching to a known shape, and missing that the real flow routes elsewhere. `orient` is the cheap step that prevents the expensive mistake. **Understand the whole thing first; the smallest diff in the wrong place is a second bug.**

Three layers, cheapest first. Use whichever exist — each degrades gracefully.

## 1. The structure map — "what connects to what"

- **If a code graph exists** (e.g. `graphify-out/graph.json` from [graphify](https://github.com/), or any repo map): query it before grepping. `graphify query "<question>"` for a scoped subgraph, `graphify path "A" "B"` to see how two things connect, `graphify explain "<concept>"`. Go straight to raw files only for known specific lines.
- **Otherwise**: a fast breadth pass — read the entry points, follow the imports, trace the actual call path end to end *once* before editing. A search agent that returns "where the flow lives" beats reading ten files yourself.
- **After structural changes** (new/moved/deleted functions or files): refresh the map so it stays true (`graphify update .` is free/no-LLM). A stale map is worse than none.

## 2. The decisions layer — "why is it like this"

Code shows *what*; it rarely shows *why*. Before changing something that looks wrong, check whether it was a deliberate decision.

- **If a decisions/incidents wiki exists** (an Obsidian vault, `docs/adr/`, `.omc/wiki`, etc.): search it first — `wiki_query "<topic>"` or plain search. The thing you're about to "fix" may be load-bearing.
- **After the work**: record any non-obvious decision or incident so the next person (or session) inherits the *why*, not just the diff. Pair a code map with a human-browsable view when you can (e.g. graphify's Obsidian export) so the map never lags the graph.

## 3. The memory layer — "what did we already learn"

Cross-session lessons live in the memory bank (see `modus:memory-loop`). Before starting, recall relevant memories; a recalled memory that names a file or flag is a hypothesis to **verify against current reality**, not a fact to trust blindly — it reflects what was true when written.

## The one rule

Orient in proportion to unfamiliarity. A file you wrote an hour ago needs none. A subsystem you've never opened needs all three layers. When unsure, spend the cheap minute — it is always less than the cost of the wrong fix.

<!-- modus: this skill is a checklist, not a tool. It routes to whatever map/wiki/memory the project has and says "look before you leap" — the single highest-leverage habit in the method. -->
