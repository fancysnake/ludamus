# Refinement checklist

Items `/tbd-refine` walks against each landed bullet. Trim or grow as the
project teaches you what you keep forgetting.

## Default items

- **Translations** — user-facing strings wrapped, i18n files updated.
- **Migrations** — schema changes have a migration; reversible if possible.
- **Error handling** — failure paths return useful errors; no silent swallows.
- **Accessibility** — keyboard reachable, semantic HTML, alt text on images.
- **Telemetry** — meaningful events logged for the new path.
- **Security** — authz checked; no new secrets in code.
- **Tests** — happy path covered; one edge case at minimum.

## Project-specific items

<Add as the project teaches you. Examples: "uploaded files
antivirus-scanned", "any new admin route gates on `Admin::Authorize`",
"feature flags default off in prod".>
