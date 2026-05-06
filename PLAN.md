# iOS staging reproduction plan

Target: iOS Simulator, Safari, `https://test.zagrajmy.net`.

## Reproduction steps

Run:

```bash
scripts/reproduce-ios-modal-bugs.sh
```

The script uses the remaining iOS 26.4 `iPhone 17 Pro` simulator by default:

`DB367B59-DFC1-4DE9-B1AF-C5FDD2F5985F`

Override with `UDID=...`, `SESSION=...`, or `BASE_URL=...` if needed.

It:

1. Opens Safari at `https://test.zagrajmy.net`.
2. Opens the first past event: **Sesje RPG w Mistrzu i Małgorzacie**.
3. Scrolls down until **Przygoda w Mieście Neonów** is visible.
4. Clicks **Open details for Przygoda w Mieście Neonów**.
5. Swipes down to bring the modal content into view.
6. Tries to click the top-right **X / Close** button.

## Bugs observed

1. The modal **X / Close** button does not close the modal on iOS Safari.
2. The modal content headed by:

   ```markdown
   ## About this session
   Przygoda w stylu Jumanji
   ```

   is not initially visible in the modal on iOS Safari; the user must swipe down to reveal it.
