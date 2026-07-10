# Security

pantheon runs hooks on every prompt and stop, so it deserves scrutiny — the whole surface is ~4k lines of stdlib Python you can audit in one sitting: [`hooks/`](hooks/), [`lib/`](lib/), [`scripts/`](scripts/).

**Trust model, in short:** everything stays local (`~/.claude/pantheon/`). The only network call is an opt-out daily version check (2s timeout). Team packs are repo-committed data — imported lessons are weight-clamped, length-capped, and quarantined to the repo that shipped them; pack "standards" are injected as project conventions that never override the user. `pack init` never exports auto-captured text unless you pass `--include-captured`.

**Reporting:** open a [GitHub security advisory](https://github.com/MiracleWeb3/pantheon/security/advisories/new) or a plain issue if it's not sensitive. Include `pantheon doctor` output when relevant. Fixes to injection surfaces, store-poisoning paths, or gate bypasses get priority over everything else.
