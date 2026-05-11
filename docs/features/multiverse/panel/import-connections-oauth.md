---
status: draft
updated: 2026-05-11
---

# Import connections — OAuth auth model

V1 connections only accept service-account JSON keys, which forces every
sphere to manage a Google service account and share forms / sheets with
its email. OAuth lets a manager click "Authorise with Google" and grant
access from their personal identity instead.

## Pick auth model at creation

As a sphere manager, I want to pick between service-account and OAuth
when creating a connection, so that I am not forced into the model that
fits my organisation worse.

- Create-connection form exposes a radio toggle: service account / OAuth
- Selecting service account shows the JSON-key paste field that v1
  already ships
- Selecting OAuth shows an "Authorise with Google" button that launches
  the consent flow and stores the resulting refresh token in the same
  encrypted-at-rest field
- Same auth-check gate runs against whichever credential type landed;
  save still blocked until `ok`

## Re-authorise an OAuth connection

As a sphere manager whose OAuth grant was revoked, I want to re-authorise
without recreating the connection, so that event services pointing at
this connection stay wired up.

- Edit form for an OAuth-backed connection shows "Re-authorise with
  Google" instead of a credential paste field
- Re-auth completes through Google's consent flow, replaces the stored
  refresh token, and runs the auth check before save
