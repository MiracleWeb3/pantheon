---
name: spartan-help
description: >
  Quick-reference card for all spartan modes, skills, and commands.
  One-shot display, not a persistent mode. Trigger: /spartan-help,
  "spartan help", "what spartan commands", "how do I use spartan".
---


> *pantheon-native name — this skill ships as `ponytail-help` in its source (see CREDITS.md for attribution).*

# Spartan Help

Display this reference card when invoked. One-shot, do NOT change mode,
write flag files, or persist anything.

## Levels

| Level | Trigger | What change |
|-------|---------|-------------|
| **Lite** | `/spartan lite` | Build what's asked, name the lazier alternative in one line. |
| **Full** | `/spartan` | The ladder enforced: YAGNI → stdlib → native → one line → minimum. Default. |
| **Ultra** | `/spartan ultra` | YAGNI extremist. Deletion before addition. Challenges requirements before building. |

Level sticks until changed or session end.

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| **spartan** | `/spartan` | Lazy mode itself. Simplest solution that works. |
| **spartan-review** | `/spartan-review` | Over-engineering review: `L42: yagni: factory, one product. Inline.` |
| **spartan-audit** | `/spartan-audit` | Whole-repo over-engineering audit: ranked list of what to delete. |
| **spartan-debt** | `/spartan-debt` | Harvest `spartan:` shortcut comments into a tracked ledger. |
| **spartan-gain** | `/spartan-gain` | Measured-impact scoreboard: less code, less cost, more speed. |
| **spartan-help** | `/spartan-help` | This card. |

Codex uses `@spartan`, `@spartan-review`, and `@spartan-help`; Claude Code
and OpenCode use the slash-command forms above (OpenCode ships all six as
slash commands).

## Deactivate

Say "stop spartan" or "normal mode". Resume anytime with `/spartan`.
`/spartan off` also works.

## Configure Default Mode

Default mode = `full`, auto-active every session. Change it:

**Environment variable** (highest priority):
```bash
export SPARTAN_DEFAULT_MODE=ultra
```

**Config file** (`~/.config/spartan/config.json`, Windows: `%APPDATA%\spartan\config.json`):
```json
{ "defaultMode": "lite" }
```

Set `"off"` to disable auto-activation on session start, activate manually
with `/spartan` when wanted.

Resolution: env var > config file > `full`.

## Update

Enable auto-update once: open `/plugin`, go to Marketplaces, pick spartan, Enable auto-update. Claude Code then pulls new versions at startup (run `/reload-plugins` when it prompts). Manual refresh: `/plugin marketplace update spartan` then `/reload-plugins`.

If `/plugin` is not recognized, your Claude Code is out of date. Update it (`npm install -g @anthropic-ai/claude-code@latest`, or `brew upgrade claude-code`) and restart. Other hosts use their own update flow.

## More

Full docs + examples: https://github.com/DietrichGebert/spartan
