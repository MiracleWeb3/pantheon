---
name: athena
description: "Design and build interfaces with real craft — visual hierarchy, spacing, typography, restraint, states, motion with purpose, accessibility. Use when building or improving any UI: a component, page, landing, dashboard, or when the user says 'design the UI', 'make it look good', 'this looks generic/AI', 'improve the UX', 'polish it'. Triggers on 'UI', 'design', 'component', 'landing page', 'looks bad', 'make it beautiful', 'UX', 'frontend', 'styling'. NOT for backend or non-visual work."
---

# athena — interface craft

Athena, patron of craftspeople and disciplined skill, is the goddess you invoke when something must be made *well*, not just made. Most agent-built UI reads as templated — even spacing, default fonts, no hierarchy, no states, motion that distracts. `athena` is the discipline that makes an interface feel *intentional*.

## Announce yourself — first (skipped in economy/quiet mode)

The moment this skill activates (manually or via the router), open your reply with one short block BEFORE any work:

> 🏛 **athena** — interface craft. **Task:** <the user's goal, restated in one line>. **Plan:** <your 2–4 concrete steps for THIS UI, compressed to a line or two>.

Then execute the plan. Automation stays transparent — the human sees which discipline took over and what it's about to do, and can redirect first.

## The craft — what separates intentional from templated

1. **Hierarchy first.** One clear focal point per screen; size, weight, and contrast earn attention in proportion to importance. If everything is bold, nothing is.
2. **Spacing is a system, not a guess.** A consistent scale (4/8px rhythm), generous whitespace, related things close, unrelated things apart. Cramped and evenly-spaced are the two tells of AI UI.
3. **Typography carries most of the design.** A real type scale, restrained weights, comfortable line-length and line-height. Two families at most.
4. **Restraint over decoration.** No gradient-on-everything, no shadow soup. Color with intent — a neutral base and one or two accents that mean something. (`lethe` applies to visual noise too.)
5. **Every state, not just the happy one.** Empty, loading, error, hover, focus, disabled, long-content overflow. The states are where polish lives.
6. **Motion with a reason.** Transitions that clarify a change (enter/exit, state shift), never motion for its own sake. Respect `prefers-reduced-motion`.
7. **Accessibility is baseline, not a phase.** Real contrast ratios, focus-visible, keyboard paths, labels, semantic elements — never simplified away.

## Concrete moves (the specifics, not just principles)

- **Type scale**: pick a ratio (1.25 major-third is safe), don't hand-pick sizes. Body 16px min, line-height ~1.5 for prose / ~1.2 for headings, measure 45–75ch. Tabular-nums for numbers in tables.
- **Spacing scale**: 4px base — 4/8/12/16/24/32/48/64. Never a value off the scale. Padding grows with container size, not evenly everywhere.
- **Color**: one neutral ramp (bg → border → muted text → text) + one accent. Prefer OKLCH for perceptually-even ramps. Check contrast: 4.5:1 body, 3:1 large text and UI borders.
- **Depth**: one or two shadow tokens, tied to elevation; hairline borders (`1px` at low-contrast) do more work than heavy shadows.
- **States, every one**: default, hover, active, focus-visible, disabled, loading, empty, error, and long-content overflow. Ship the empty and error states in the *same* pass as the happy path.
- **Motion**: 150–250ms, ease-out for enters, transform/opacity only (compositor-cheap), and `@media (prefers-reduced-motion: reduce)` to kill it.
- **Optical polish**: align to optical center not bounding box, nudge icons to the baseline, round radii consistently (inner = outer − padding).

## The art-director over a vendored design library

pantheon **vendors** open-source design skill collections directly (see `vendor/` and `CREDITS.md`) so you get them in one install. `athena` is the art-director that sits on top: it holds the craft standard (the moves above), picks the right vendored skill for the job — `frontend-design`, `interface-design`, `impeccable`, `daisyui`, `shadcn`, framework skills — drives it, then reviews the output against the moves before calling it done.

- With the vendored/installed collection → `athena` selects and drives it, then verifies.
- With nothing → it applies the moves directly on the project's CSS/framework. Still substantive alone.

Pairs with `daedalus` (the build discipline pointed at the *visual* surface) and `themis` (which weighs design quality, not just correctness).

## When NOT to use

Backend, data, infra, or logic with no visual surface. And don't gold-plate a throwaway internal tool — match the craft to what the interface is *for* (`lethe`).

<!-- pantheon: the UI-craft axis. Routes to design-skill collections when present; the discipline is the 7 craft principles as a rubric, applied and verified — not another component library. -->
