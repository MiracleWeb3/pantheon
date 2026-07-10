---
name: mnemosyne
description: "Compound what you learn across sessions -- capture corrections as they happen, consolidate into memory, promote what recurs into always-loaded rules. Use when the user corrects you, states a preference, or says 'remember this'. Triggers: 'remember', 'you keep', 'from now on'."
---

# mnemosyne — the mother of memory

Mnemosyne, Titan goddess of memory, was mother to the nine Muses — nothing is created without her. An agent's weights are frozen, but an always-loaded instructions file plus a memory bank *are* a learning layer: anything durable written there conditions every future session, which is behaviorally a fine-tune. This skill runs that loop — capture after each turn, apply next session.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **mnemosyne** — the mother of memory. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS task, compressed to a line or two>.

Then execute the plan. This keeps automation transparent — the human always sees which discipline took over, what it understood, and what it is about to do, and can redirect before any work happens. One block, no ceremony beyond it: announce, then act. (Goal here: "capture what was learned and make it durable.")

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

## Receipt — file your footprint (skipped in quiet mode)

When the task completes (or you hand back), file ONE honest line via Bash:

`~/.claude/pantheon/bin/pantheon receipt add --skill mnemosyne --note "<what was done or caught, one line>"`

Good notes are outcomes, not activity: "root-caused reap loop, sealed with regression test", "deleted 340 dead lines", "flagged auth bypass in review". If the command doesn't exist yet (first session after install), skip silently — bookkeeping must never block or delay the actual work.
