# Testing Strategy

## Unit tests

Cover: mills (public methods and functions).

Rules:

- mock at highest level
- assert all mock calls
- no database

## Integration tests

Cover: gates (views), links (public methods and functions).

Rules:

- mock at lowest level, or not at all — use test db, `responses`, or dedicated
  mock package
- assert all mock calls
- assert all side effects

### Views and commands

Verify view→template **context contract**: views produce the right data for
every branch.

Structure: `{subdomain}/{bounded_context}/test_url_name.py`

Rules:

- use `assert_response`
- `ANY` only when objects are incomparable
- one test per meaningful context branch (empty vs populated, roles,
  permissions, edges)

Rendered-page behavior belongs in e2e.

### Links

Verify driven adapters against real infrastructure.

Structure: mimic code.

Skip: one-liners, conditional-free / error-free functions (thin SDK wrappers).

## End-to-end tests

Cover: gates. Playwright (TypeScript).

Verify **features work** in a real browser.

Scope: operations and workflows (create, edit, delete, filter, navigate).
Combine related actions per test (apply several filters at once; create then
edit).

Per-branch context coverage belongs in integration.

## Migration to the new strategy

1. Move current integration tests to the right directories and files.
2. Drop tests that no longer fit, or move them to unit tests.
3. Reach 100% component-test coverage.
4. Add e2e tests for current dynamic features.
