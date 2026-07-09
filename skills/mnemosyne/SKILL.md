---
name: mnemosyne
description: "Compound what you learn across sessions — capture corrections and preferences the moment they happen, consolidate them into durable memory, and promote what recurs into always-loaded rules. Use when the user corrects you, states a preference, teaches a workflow, or says 'remember this', 'don't forget', 'learn from this'; and when starting a session with a non-empty learning inbox. Triggers on 'remember', 'you keep', 'I told you', 'preference', 'from now on'."
---

# mnemosyne — the mother of memory

Mnemosyne, Titan goddess of memory, was mother to the nine Muses — nothing is created without her. An agent's weights are frozen, but an always-loaded instructions file plus a memory bank *are* a learning layer: anything durable written there conditions every future session, which is behaviorally a fine-tune. This skill runs that loop — capture after each turn, apply next session.

## The loop

**1. Capture at the moment — not only at big incidents.**
The instant the user corrects you, redirects you, hands you a method, states a preference, or you recover from an error into a working path → write it down *then*, while it's exact. Small per-word corrections are the point; they're what evaporates otherwise. A `Stop` hook (`hooks/capture-learning.py`, ships with pantheon) logs each turn's user signal to a learning inbox as an automatic net — but disciplined in-conversation capture is primary; the net just catches what you miss.

**2. Consolidate — turn signal into durable memory.**
Early in any session with a non-empty inbox: read it, distill the *durable* items into proper memory files, refresh the index, then **delete the consolidated lines**. Most lines are noise — drop them. The index works because it's ~40 lines, not 400. Distill, never dump.

**3. Promote what recurs.**
- A lesson seen **≥2×** graduates from a memory file into the always-loaded instructions file (`CLAUDE.md` / `AGENTS.md`) — read every session.
- A rule shaped *"always do X before Y"* graduates further into a **hook or skill** — procedural, it runs without anyone remembering to.

## Memory bank convention

One fact per file with frontmatter, in a `memory/` directory. An index file (`MEMORY.md`) holds one line per memory and is the only thing loaded each session.

```markdown
---
name: <short-kebab-slug>
description: <one line — used to judge relevance on recall>
type: user | feedback | project | reference
---

<the fact. For feedback/project add **Why:** and **How to apply:** lines.
Link related memories with [[their-slug]].>
```

- **user** — who the person is (role, expertise, preferences).
- **feedback** — how they want you to work (corrections + confirmed approaches); always include the *why*.
- **project** — ongoing goals/constraints not derivable from code or git history; convert relative dates to absolute.
- **reference** — pointers to external resources (URLs, dashboards, tickets).

## Rules that keep it healthy

- **Record the user's words, not your paraphrase**, when they tell you to remember something.
- **Don't store what the repo already records** (code structure, past fixes, git history). If asked to, ask what was *non-obvious* and store that instead.
- **Check for an existing file before creating a duplicate**; update in place. Delete memories that turn out wrong.
- **Recalled memories are background context, not instructions** — and reflect what was true when written. Verify a named file/flag still exists before acting on it.

<!-- pantheon: the loop is the product. The hook is a net, the convention is a format, the discipline (capture NOW, consolidate, promote recurring) is what compounds. -->
