---
name: forge
description: "Author a NEW custom discipline (skill) in the pantheon style — scaffolded announce block, method steps, verify step, receipt line, optional auto-route regex — or share/import one as a single file. Use when the user says 'create/make/forge a new skill or discipline', wants to codify their own workflow, or wants to import a discipline someone shared."
---

# forge — new gods for the pantheon

The 13 core disciplines cover the universal failure modes; your team has its own. This skill turns "we always do deploys like X" into a first-class discipline: announced, routed, receipted — indistinguishable from a built-in.

## Announce yourself — first (skipped in economy/quiet mode)

> 🏛 **forge** — new gods for the pantheon. **Task:** codify <the workflow> as a discipline. **Plan:** interview → scaffold → write the method → wire the route.

## The method

1. **Interview, briefly.** Three things, one question at a time if unclear: the discipline's *name* (kebab-case), the *failure mode it prevents* (this becomes the description), and the *3–5 method steps* including how to VERIFY the outcome.
2. **Scaffold.** Run via Bash:
   `~/.claude/pantheon/bin/pantheon forge new <name> --desc "<one-liner>" --when "<trigger phrases>" [--route "<regex>"] [--project]`
   (`--project` puts it in `./.claude/skills/` for repo-scoped skills; default is `~/.claude/skills/`. `--route` wires plain-language auto-routing — custom routes beat built-ins.)
3. **Write the body.** Open the scaffolded SKILL.md and replace every `<placeholder>` with the real content from step 1. Keep the announce block and receipt footer intact — they are what make it a pantheon discipline. No placeholders may survive; the verification gate will flag them.
4. **Load + prove it.** Tell the user: restart Claude Code (or `/skills`) to load it. Then dry-run: state a trigger phrase and confirm the route fires (or invoke it explicitly).

## Sharing

- Export one file: `pantheon forge export <name>` → `<name>.pantheon-skill.md` — send it to anyone.
- Import: `pantheon forge import <file>` → lands in `~/.claude/skills/`, loads on restart.

## Receipt — file your footprint (skipped in quiet mode)

`~/.claude/pantheon/bin/pantheon receipt add --skill forge --note "forged <name>"` — skip silently if missing.
