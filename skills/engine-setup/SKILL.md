---
name: engine-setup
description: Use first for install/update routing — sends setup, doctor, or MCP requests to the correct OMC setup flow
level: 2
---


> *pantheon-native name — this skill ships as `setup` in its source (see CREDITS.md for attribution).*

# Setup

Use `/pantheon:engine-setup` as the unified setup/configuration entrypoint.

## Usage

```bash
/pantheon:engine-setup                # full setup wizard
/pantheon:engine-setup doctor         # installation diagnostics
/pantheon:engine-setup mcp            # MCP server configuration
/pantheon:engine-setup wizard --local # explicit wizard path
```

## Routing

Process the request by the **first argument only** so install/setup questions land on the right flow immediately:

- No argument, `wizard`, `local`, `global`, or `--force` -> route to `/pantheon:engine-install` with the same remaining args
- `doctor` -> route to `/pantheon:engine-doctor` with everything after the `doctor` token
- `mcp` -> route to `/pantheon:mcp-setup` with everything after the `mcp` token

Examples:

```bash
/pantheon:engine-setup --local          # => /pantheon:engine-install --local
/pantheon:engine-setup doctor --json    # => /pantheon:engine-doctor --json
/pantheon:engine-setup mcp github       # => /pantheon:mcp-setup github
```

## Notes

- `/pantheon:engine-install`, `/pantheon:engine-doctor`, and `/pantheon:mcp-setup` remain valid compatibility entrypoints.
- Prefer `/pantheon:engine-setup` in new documentation and user guidance.

Task: {{ARGUMENTS}}
