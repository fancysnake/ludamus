# /tbd-plan

Produce `.tbd/plan.md` — a thin, condensed delta describing what this
bullet changes. Overwrites any existing plan.

## Input

A target user story (feature file + story title or index). If ambiguous, ask.

## What you do

1. Read the targeted feature file.
2. Read the codebase enough to know what this change touches.
3. Write `.tbd/plan.md` with three sections:
   - **Change** — the delta, in the codebase's language. Names files,
     models, fields, routes, components. Specific.
   - **Touchpoints** — integration points with existing code, only when
     there's real risk. Skip if self-contained.
   - **Deferred** — what's punted from this bullet, named so `/tbd-refine`
     can find it.
4. If `.tbd/` doesn't exist, create it. If `.tbd/` is not in `.gitignore`,
   add it.

## Tone

The plan is a commitment, not a briefing. The model reading it already
knows the project. Cut everything that isn't the delta.

Bad: "The project uses Rails with PostgreSQL. The User model is in
`app/models/user.rb`. We will add an avatar URL field to allow users to set
profile pictures."

Good: "Add `avatar_url:string` to `User`. Edit form gets URL input +
`<img>` preview when set."

## Length

Typical: 5–15 lines. Tricky: up to 30. Hitting 60 means the bullet is too
big — stop and tell the user to split the story before planning.

## Don'ts

- No project background. No architecture recap. No glossary.
- No "approach" or "rationale" sections. The plan describes what changes, not why.
- No checklists of standard concerns. Those live in `CHECKLIST.md`.
