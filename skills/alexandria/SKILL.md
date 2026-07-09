---
name: alexandria
description: "Maintain a persistent project knowledge base — curated prose pages on architecture, domain, decisions, and incidents that compound across sessions (the Karpathy 'LLM wiki' model). Use when documenting how something works, when the user says 'write this to the wiki', 'document this', 'what do we know about X', or when a hard-won understanding should outlive the session. Triggers on 'wiki', 'document', 'write it down', 'knowledge base', 'how does our X work', 'ADR', 'decision record'. Distinct from mnemosyne (atomic facts) and arachne (the code graph)."
---

# alexandria — the great library

The Library of Alexandria tried to hold everything known, curated and cross-referenced. `alexandria` is that for a project: a durable, human-and-agent-browsable wiki of *how this system actually works* — the prose layer of knowledge that a fresh context can read to get years of understanding in minutes. This is Karpathy's "LLM wiki" idea: the agent maintains a Markdown knowledge base it reads before working and writes after learning, so understanding **compounds** instead of evaporating each session.

## Announce yourself — first (skipped in economy/quiet mode)

> 🏛 **alexandria** — the great library. **Task:** <restate the goal>. **Plan:** <2–4 steps: which pages to read/write>.

Then execute.

## Where it sits in the knowledge stack

pantheon keeps three knowledge layers distinct — they compose, they don't overlap:

- **`arachne`** — the **structure** (a code graph: what calls what). Machine-navigable.
- **`alexandria`** — the **prose** (this skill): *why* it's built this way, how a subsystem works, what an incident taught. Human-readable pages.
- **`mnemosyne`** — the **facts** (memory bank): atomic corrections, preferences, one fact per file.

`ariadne` reads all three to orient before work.

## The loop

1. **Query before you work.** Search the wiki for the subsystem/topic first — a five-minute read of an existing page beats re-deriving it (and prevents "fixing" a deliberate decision).
2. **Write after you learn.** When you finish something non-obvious — an architecture, a gnarly flow, a decision with real tradeoffs, an incident and its fix — capture it as a page *while it's fresh*.
3. **Curate, don't dump.** One topic per page, a clear title, cross-links between pages (`[[wiki-links]]`). Prune stale pages. A wiki no one can navigate is a graveyard; keep it distilled.

## Page anatomy

```markdown
# <Topic> — <one-line what-this-is>

## Context      — why this exists, what problem it solves
## How it works — the mechanism, the real flow, key files
## Decisions    — what was chosen and *why*, alternatives rejected
## Gotchas      — incidents, sharp edges, things that look wrong but aren't

Links: [[related-page]] · code: `path/to/file.py:linenum`
```

Categorize pages (architecture / decision / debugging / convention) so the index stays scannable.

## Composes with your stack

- **`oh-my-claudecode` wiki** (`wiki_query`, `wiki_read`, `wiki_ingest`) — `alexandria` drives it: query at start, ingest at end.
- **An Obsidian vault / `docs/adr/`** — treat it as the wiki; `[[wiki-links]]` are Obsidian-native, so the pages render as a navigable graph for humans too.
- **Nothing installed** → a plain `wiki/` or `docs/` folder of Markdown with an index page.

## When NOT to use

Don't wiki what the code already says plainly, or a throwaway one-off. Capture the *non-obvious why*, not a paraphrase of the diff — that's `lethe` applied to documentation.

<!-- pantheon: the Karpathy LLM-wiki / prose-knowledge layer. Routes to OMC wiki or an Obsidian vault; the discipline is query-before / write-after / curate-don't-dump. Compounds understanding across sessions. -->

## Receipt — file your footprint (skipped in quiet mode)

When the task completes (or you hand back), file ONE honest line via Bash:

`~/.claude/pantheon/bin/pantheon receipt add --skill alexandria --note "<what was done or caught, one line>"`

Good notes are outcomes, not activity: "root-caused reap loop, sealed with regression test", "deleted 340 dead lines", "flagged auth bypass in review". If the command doesn't exist yet (first session after install), skip silently — bookkeeping must never block or delay the actual work.
