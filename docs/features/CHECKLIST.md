# Refinement checklist

Items `/tbd-refine` walks against each landed bullet. Trim or grow as the
project teaches you what you keep forgetting.

## Default items

- **Implementation-agnostic language** — scan stories for UI elements,
  interface verbs, internal tech names, model or field names, and
  literal button text. Would each story still hold on iOS or a CLI?
- **Story-only structure** — no context paragraphs, no motivation
  prose, no buried rules. H2 groups related stories by topic, never
  labels a single story.
- **Translations** — user-facing strings wrapped, i18n files updated.
- **Migrations** — schema changes have a migration; reversible if possible.
- **Error handling** — failure paths return useful errors; no silent swallows.
- **Accessibility** — keyboard reachable, semantic HTML, alt text on images.
- **Telemetry** — meaningful events logged for the new path.
- **Security** — authz checked; no new secrets in code.
- **Tests** — happy path covered; one edge case at minimum.

## Project-specific items

- **"test" reserved for pytest** — no production symbol, column, or
  field uses `test` / `tested`; use `check` / `validation` /
  `verification` instead.
- make sure the view permissions are correctly checked to not allow editing one
  event or sphere from another.
