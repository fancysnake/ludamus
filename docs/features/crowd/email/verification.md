---
status: draft
updated: 2026-05-07
---

# Email verification

Ludamus stores user emails on the User model with no proof of ownership.
Auth0 sign-ins arrive pre-verified, but emails set or changed via the
profile form are unverified. We need verification with a safe change
flow that locks both the old and new address during transition, plus a
soft nudge that doesn't block usage.

## As a user, I want to verify my email, so the system trusts I own it

- After my email is set or changed, a verification link is sent to that
  address
- Clicking the link marks the email verified
- The link expires 48 hours after issue
- An expired or unknown token shows an error and offers to resend

## As a user, I want to change my email safely, with no hijack window

- Submitting a new email on the profile form does not replace the current
  one immediately
- The new email is reserved (cannot be claimed by another account) while
  pending
- The old address receives a notification with a cancel link
- The cancel link works without login — token-only authentication, since
  the old-email owner may have lost access
- Verifying the new address swaps it in as primary and notifies the old
  address that the change is complete
- Cancelling discards the pending new email; the primary is unchanged

## As an unverified user, I want a soft nudge, not a hard block

- A banner appears on every page for logged-in users with an unverified
  primary email
- The banner offers an inline "Resend verification email" action
- I can dismiss the banner; it stays dismissed for 7 days, then reappears
  if still unverified
- All other features remain usable while unverified

## As a user, I want to resend my verification email

- "Resend verification" is reachable from the profile page and from the
  soft-block banner
- Resending replaces the previous token; old links stop working
- I'm returned to the page I was on with a confirmation message

## As an Auth0 user, I want my email auto-verified

- New Auth0 sign-ups land with their primary email already verified
- Existing users whose Auth0 profile carries the same email are marked
  verified on their next login

## As an operator, I want to send verification emails in bulk

- A `sendverification` management command queues verification emails for
  all users with an unverified primary email
- A `--dry-run` flag reports what would be sent without sending
- The command reports how many emails were dispatched
