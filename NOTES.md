# PR report: iOS Safari modal hit-testing regression

## Summary

This PR fixes an iOS Safari simulator bug where session modals rendered correctly but taps landed on the underlying scrolled page instead of the modal top layer.

The working fix is to make the root document scrolling model explicit:

```css
html,
body {
  height: 100%;
  overflow-y: scroll; /* must be scroll, not auto */
  -webkit-overflow-scrolling: touch;
}
```

## User-visible symptoms

On iOS Safari, after scrolling the event page and opening a session detail modal:

- tapping the top-right **X / Close** button did nothing;
- tapping the **Participants** tab did nothing;
- refreshing the page often made the X clickable again;
- the issue reproduced only after opening the modal from a scrolled page.

## Root cause hypothesis

The bug appears to be an iOS Safari hit-testing mismatch between:

1. the visual position of a native `<dialog>` in the browser top layer, and
2. the underlying document scroll coordinate space used for pointer/touch hit testing.

A temporary tap-debug overlay showed that taps on the visible modal controls were resolved to underlying page content, for example `span.truncate` or `html`, rather than `[data-modal-close]` or the tab button.

The debug overlay also showed non-zero document scroll, e.g.:

```text
scroll: 0,1009
```

That matched the manual observation: the bug appeared only after scrolling past normal page boundaries before opening the modal.

## What we ruled out

### Not caused directly by scroll locking

Disabling the modal scroll-locking code did **not** make the X button clickable. So the issue was not directly caused by `@fluejs/noscroll`.

### Not solved by larger close hit targets

The close button hitbox was initially small, but the tap-debug overlay showed taps were not merely missing a small button. Safari was hit-testing against the wrong layer/coordinate space.

### Separate `scrollview-fade` issue

`scrollview-fade` can still affect modal panel painting on iOS Safari. Removing it made the Information tab content appear consistently during debugging, but we are keeping the fade and tracking that as a separate rendering/polish issue.

## Fix

Set root scrolling explicitly on both `html` and `body`:

```css
html,
body {
  height: 100%;
  overflow-y: scroll;
  -webkit-overflow-scrolling: touch;
}
```

This makes Safari keep visual rendering and hit testing aligned when opening native `<dialog>` modals from a scrolled page.

## Regression coverage

`scripts/reproduce-ios-modal-bugs.ts` now reproduces the real user path:

1. opens the event page without the `?session=...` shortcut;
2. scrolls until **Przygoda w Mieście Neonów** is in view;
3. opens the modal from the session card;
4. verifies Information content is visible;
5. taps the Close button;
6. fails if the modal is still open.

Validation performed locally:

- With the CSS fix temporarily removed, the script failed with:

  ```text
  Reproduced iOS modal bug(s):
  - The modal X / Close button did not close the modal.
  ```

- With the CSS fix restored, the script passed:

  ```text
  No iOS modal bugs reproduced.
  ```

## CI

The iOS regression script is run by `.github/workflows/mobile.yml` on macOS against the local e2e server.

## Notes for future debugging

Useful search terms:

- `iOS Safari dialog showModal hit testing scrolled page`
- `Safari top layer dialog hit testing scroll offset`
- `iOS Safari fixed dialog click offset scrollY`
- `HTML dialog visual viewport scroll hit test bug`
