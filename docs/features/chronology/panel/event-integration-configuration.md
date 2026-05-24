---
status: in-progress
updated: 2026-05-23
---

# Event integration configuration

As an organiser, I want to see the integrations currently attached to an
event, so that I know which external systems the event can speak through.

As an organiser, I want to attach an external-system integration to an
event, so that the event has a configured channel through which pipelines
can speak to that system.

As an organiser, I want to change an existing integration's configuration,
so that I can repoint it without recreating it.

As an organiser, I want to remove an integration from an event, so that
the event stops speaking through a channel that is no longer relevant.

As an organiser, I want to verify that an integration can reach what it
needs, so that I know whether it will work before saving it.

As an organiser, I want a failed verification to tell me what went wrong
and how to fix it, so that I'm not guessing about credentials,
permissions, or missing resources.

As an organiser, I want the system to refuse to save an integration that
has not passed verification, so that broken configurations never reach
the pipeline.

As an organiser, I want changes that cannot affect connectivity to not
demand fresh verification, so that I can fix a typo without re-testing
everything.

As an organiser, I want each integration on an event to have a distinct
name, so that I can tell them apart.
