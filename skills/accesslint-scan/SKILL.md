---
name: accesslint-scan
description: "Audit a live page for accessibility issues, by URL, config target, or the config's default. Returns live-DOM WCAG violations with DOM selector and file:line. Locates; doesn't edit. Use for \"is this page accessible\" or to verify a UI change. For uncommitted changes, use `diff` instead."
argument-hint: "[target|url]"
allowed-tools: Bash, Read, Glob, Grep, Skill, Task
---

Audit a live page and report what's broken and where. Locate; don't fix.

`$ARGUMENTS` is a URL, a config **target name** (`dev`, `storybook`, …), or empty to audit the **default target** from `accesslint.config.json`. If it's empty and no config exists, ask for a URL or suggest `npx @accesslint/cli init` to set targets up.

## 1. Audit

```bash
PORT=$(npx -y @accesslint/chrome@latest ensure | node -e 'process.stdin.on("data",d=>process.stdout.write(""+JSON.parse(d).port))')
npx -y @accesslint/cli@latest scan <target> --port "$PORT" --format json
```

`<target>` is the URL or config target name from `$ARGUMENTS`; **omit it** (don't pass `""`) to audit the config's default target. Flags as needed: `--selector`, `--wait-for "<selector>"`, `--include-aaa`, `--disable <rules>` — or pin them per-target in `accesslint.config.json`.

## 2. Report

Counts by impact, then one entry per violation:

- **where** — selector verbatim + `file:line (symbol)` if `source` is present — never fabricate. If no violation has `source`, note "source mapping unavailable — located by selector only".
- **evidence** — contrast ratio, missing attribute, empty name
- **fix** — mechanical change or `NEEDS HUMAN`

Don't edit. For fixes: apply mechanical ones then re-run to verify; for bulk work hand off to `accesslint:audit`.

## 3. Tear down

```bash
npx -y @accesslint/chrome@latest stop --all  # skip if ensure reported "managed":false
```

## Gotchas

- `ensure` always determines the port — never hardcode 9222.
- CLI exit 2 = bad URL/target or page never loaded; check the dev server. An unknown target name makes the CLI list the available targets from `accesslint.config.json`.
