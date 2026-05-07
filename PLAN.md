# iOS modal reproduction plan

Target: iOS Simulator, Safari, `http://localhost:8000` by default.

## Reproduction steps

Start the local e2e server:

```bash
mise run boot-e2e
```

In another shell, run:

```bash
scripts/reproduce-ios-modal-bugs.ts
```

The script uses local e2e seed data:

1. Verifies the local event page is reachable and contains **Przygoda w Mieście Neonów**.
2. Opens Safari at `http://localhost:8000/chronology/event/autumn-open/`.
3. Scrolls to **Przygoda w Mieście Neonów** and opens the modal from the scrolled page.
4. Checks whether **About this session** / **Przygoda w stylu filmu** content is visible immediately.
5. Tries to click the top-right **X / Close** button.

Override with `BASE_URL=...`, `UDID=...`, `SESSION=...`, `IOS_DEVICE_NAME=...`, `IOS_RUNTIME=...`, `EVENT_PATH=...`, `TARGET_QUERY_PARAM=...`, or `TARGET_SESSION_TITLE=...` if needed.

## Bugs observed

1. The modal **X / Close** button does not close the modal on iOS Safari.
2. The modal content headed by:

   ```markdown
   ## About this session
   Przygoda w stylu Jumanji
   ```

   is not initially visible in the modal on iOS Safari; the user must swipe down to reveal it.
