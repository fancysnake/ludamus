# /tbd-fire

Execute `.tbd/plan.md`. Implement the change end-to-end, honestly, until
the targeted user story works.

## What you do

1. Read `.tbd/plan.md`. If missing, stop and tell the user to run `/tbd-plan`.
2. Read the targeted feature file.
3. If feature status is `draft`, flip it to `in-progress` and update the date.
4. Implement the change. Real layers, no stubs. Happy path works honestly.
   Edge cases, polish, translations, and similar may be deferred (refinement
   covers them).
5. Run tests. Run linters. Start the dev server if applicable. Walk through
   the user story manually (or describe the walkthrough if not
   interactive).
6. End with one line: `Landed: <user story title>`.

## Scope discipline

If implementation reveals a need for something outside the plan, **stop**.
Tell the user:

> This needs `<thing>`, which isn't in the current bullet. Edit the feature
> file (or run `/tbd-story` to add a story), then re-run `/tbd-plan` and
> `/tbd-fire`.

Don't widen mid-fire. Don't add scope and ask forgiveness.

## Exit criteria (all four must hold)

- Tests pass.
- Linters pass.
- Dev server runs (if applicable).
- Targeted user story is demonstrably true.

If any fails after a reasonable attempt, surface what's blocking. Don't
mark the bullet landed.

## Don'ts

- Don't update feature status to `done`. That's the user's call after the
  whole feature is whole.
- Don't run `/tbd-refine` automatically. Offer it; don't assume.
- Don't write code outside what the plan describes, even if it seems related.
