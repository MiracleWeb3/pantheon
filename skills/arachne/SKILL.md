---
name: arachne
description: "Build and maintain a navigable knowledge graph of a codebase or corpus — nodes, edges, communities — so orientation is a query instead of a blind grep. Use when the user says 'map the codebase', 'build the graph', 'graphify this', 'update the map', when entering a large unfamiliar repo, or after structural changes moved things around. Triggers on 'graph', 'map the code', 'graphify', 'knowledge graph', 'dependency map', 'visualize the codebase'. Builds the map that ariadne reads."
---

# arachne — the weaver

Arachne wove tapestries so true they rivaled the gods'; her web is a lattice of connected threads — exactly a knowledge graph, nodes joined by edges. `arachne` builds and maintains that web for a codebase or corpus so that orientation becomes a *query* ("what connects to the auth flow?") instead of a blind grep. It is the **structure** layer of pantheon's knowledge stack; `ariadne` is the skill that *reads* the web `arachne` weaves.

## Announce yourself — first (skipped in economy/quiet mode)

> 🏛 **arachne** — the weaver. **Task:** <restate the goal>. **Plan:** <2–4 steps: build / update / export / query>.

Then execute.

## The method

1. **Weave the graph** — turn the codebase (or docs, papers, a corpus) into a persistent graph of nodes and relationships, with community detection so clusters are visible. A good graph surfaces the *god nodes* (the few files everything depends on) that a file listing hides.
2. **Keep it true** — after structural changes (new/deleted/moved functions or files), refresh the graph. A stale map is worse than none — it confidently points at code that moved. Regeneration should be cheap enough to run routinely.
3. **Pair it with a human view** — export the graph to an Obsidian vault / canvas so people browse the same map agents query. The machine-readable graph and the human-browsable notes should never drift apart.
4. **Query, don't grep** — once woven, orient through it: scoped subgraphs, shortest path between two symbols, plain-language explanations of a cluster.

## Composes with your stack

- **[graphify](https://github.com/)** — the canonical weaver. `graphify .` to build, `graphify query "<q>"` / `path "A" "B"` / `explain "<concept>"` to navigate, `graphify update .` after changes (free, no-LLM), `graphify export obsidian` for the human view.
- **Any repo-map / ctags / LSP index** — use it as the graph if graphify isn't present.
- **Nothing installed** → fall back to a fast structural breadth pass (entry points → imports → call paths) and offer to set up a persistent map for next time.

`arachne` weaves; `ariadne` reads; `alexandria` annotates the *why* over the top. Together they are the map, the guide, and the legend.

## When NOT to use

A small repo you already hold in your head, or a one-file change. Weaving a graph for a five-file project is overhead `lethe` would refuse — a quick read is faster.

<!-- pantheon: the code-graph / structure layer (graphify + obsidian pairing). Routes to graphify when present. The discipline is weave → keep-true → pair-with-human-view → query-not-grep. Feeds ariadne. -->
