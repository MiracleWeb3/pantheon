---
name: setting-up
description: Project setup files including .gitignore, GitHub Actions workflows, and VS Code extensions. Use when initializing new projects or adding CI/editor config.
---

# Project Setup

## .gitignore

Create when `.gitignore` is not present:

```
*.log
*.tgz
.cache
.DS_Store
.eslintcache
.idea
.env
.nuxt
.temp
.output
.turbo
cache
coverage
dist
lib-cov
logs
node_modules
temp
```

## GitHub Actions

Add these workflows when setting up a new project. Skip if workflows already exist. All use [sxzz/workflows](https://github.com/sxzz/workflows) reusable workflows.

### Autofix Workflow

**`.github/workflows/autofix.yml`** - Auto-fix linting on PRs:

```yaml
name: autofix.ci

on: [pull_request]

jobs:
  autofix:
    uses: sxzz/workflows/.github/workflows/autofix.yml@main
    permissions:
      contents: read
```

### Unit Test Workflow

**`.github/workflows/unit-test.yml`** - Run tests on push/PR:

```yaml
name: Unit Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions: {}

jobs:
  unit-test:
    uses: sxzz/workflows/.github/workflows/unit-test.yml@main
```

### Release Workflow

**`.github/workflows/release.yml`** - Publish on tag (library projects only):

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    uses: sxzz/workflows/.github/workflows/release.yml@main
    with:
      publish: true
    permissions:
      contents: write
      id-token: write
```

## VS Code Extensions

Configure in `.vscode/extensions.json`:

```json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",
    "vue-philosophy.pnpm-catalog-lens",
    "vue-philosophy.iconify",
    "vue-philosophy.unocss",
    "vue-philosophy.slidev",
    "vue.volar"
  ]
}
```

| Extension | Description |
|-----------|-------------|
| `dbaeumer.vscode-eslint` | ESLint integration for linting and formatting |
| `vue-philosophy.pnpm-catalog-lens` | Shows pnpm catalog version hints inline |
| `vue-philosophy.iconify` | Iconify icon preview and autocomplete |
| `vue-philosophy.unocss` | UnoCSS IntelliSense and syntax highlighting |
| `vue-philosophy.slidev` | Slidev preview and syntax highlighting |
| `vue.volar` | Vue Language Features |
