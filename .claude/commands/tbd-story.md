# /tbd-story

Create or refine a feature file. Same command both ways — distinguishes
by whether the input names an existing file.

## Input

A file path, an inline description, or a reference to an existing feature file.

## What you do

**For new features:**

1. List `docs/features/` to see existing subdomains and bounded contexts.
2. Propose placement: `docs/features/<subdomain>/<context>/<name>.md`.
   Suggest an existing context when one fits. Only propose a new subdomain
   or context with explicit justification.
3. If the chosen context already has subgroups (folders), propose a
   subgroup or ask. Default is fitting existing structure; new subgroup
   requires justification.
4ss. Draft the feature file (see Shape below). Show it, ask for
   confirmation before writing.

**For refinement (existing file given):**

1. Read the file.
2. Propose changes in plain prose: amendments, splits, new stories for
   discovered edge cases, deferrals, deletions. Be specific about which
   lines change.
3. Wait for user direction. Don't apply changes unilaterally.

## Shape of a feature file

```text
status: draft
updated: YYYY-MM-DD

# <Feature name>

<One-paragraph context. Skip if obvious from title.>

## As a <role>, I want <thing>, so that <reason>

- <acceptance criterion>
- <acceptance criterion>

## As a <role>, I want <thing>, so that <reason>

- <acceptance criterion>
- <acceptance criterion>
```

One feature file = one or more user stories tied together by a shared
concern. CRUD usually = one file with four stories. A truly large feature
splits into multiple files in the same context folder.

## Don'ts

- Don't invent acceptance criteria the user didn't imply. Ask.
- Don't write Gherkin (`Given/When/Then`). User stories only.
- Don't pad with non-functional concerns (perf, security, a11y). Those go
  in `CHECKLIST.md` and surface during `/tbd-refine`.
- Don't set status to anything other than `draft` on creation.
