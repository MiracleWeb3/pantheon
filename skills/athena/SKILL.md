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

## Composes with your stack

- **Design skill collections** — [ui-skills.com](https://www.ui-skills.com/), `frontend-design`, `interface-design`, `impeccable`, and framework skills (shadcn, tailwind, etc.). `athena` orchestrates whichever are installed: pick the fitting one, apply the craft principles above as the rubric, and verify the result against them.
- **None installed** → apply the seven principles directly with the project's existing CSS/framework.

Pairs with `daedalus` (athena is the build discipline pointed at the *visual* surface) and `themis` (a review pass can weigh design-quality, not just correctness).

## When NOT to use

Backend, data, infra, or logic with no visual surface. And don't gold-plate a throwaway internal tool — match the craft to what the interface is *for* (`lethe`).

<!-- pantheon: the UI-craft axis. Routes to design-skill collections when present; the discipline is the 7 craft principles as a rubric, applied and verified — not another component library. -->
