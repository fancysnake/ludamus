import { devices, expect, test } from '@playwright/test';

test.describe('Event detail page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chronology/event/autumn-open/');
  });

  test('shows event information and enrollment banner', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Autumn Open Playtest' })).toBeVisible();
    await expect(page.getByText('Upcoming')).toBeVisible();

    const banner = page.getByRole('alert').filter({
      hasText: 'Enrollment is open—grab a slot before we fill up!',
    });
    await expect(banner).toBeVisible();
  });

  test('renders session cards with locations and opens detail modal', async ({ page }) => {
    const sessionCards = page.locator('.session-card');
    await expect(sessionCards).toHaveCount(2);

    const megaStrategyCard = sessionCards.filter({ hasText: 'Mega Strategy Lab' });
    await expect(megaStrategyCard).toContainText('Convention Center');
    await expect(megaStrategyCard).toContainText('Main Hall');
    await expect(megaStrategyCard).toContainText('East Wing');

    await megaStrategyCard.getByRole('link', { name: 'Open details for Mega Strategy Lab' }).click();

    const detailDialog = page.getByRole('dialog', { name: 'Mega Strategy Lab' });
    await expect(detailDialog).toBeVisible();
    await expect(detailDialog).toContainText('Alex Morgan');

    await detailDialog.getByRole('button', { name: 'Close' }).first().click();
    await expect(detailDialog).toBeHidden();
  });

  test(
    'keeps mobile session modal footer inside the clickable dialog bounds',
    async ({ browser, browserName }) => {
      test.skip(browserName === 'firefox', 'Firefox does not support mobile emulation');
      const context = await browser.newContext({
        ...devices['iPhone 14 Pro'],
        baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8000',
      });
      const page = await context.newPage();

      await page.goto('/chronology/event/autumn-open/');
      await page
        .locator('.session-card')
        .nth(1)
        .getByRole('link')
        .click();
      await page.waitForTimeout(1000);

      const detailDialog = page.getByRole('dialog', {
        name: 'Cozy Storytellers Circle',
      });
      const footerClose = detailDialog.getByRole('button', { name: 'Close' });
      await expect(footerClose).toBeInViewport();

      const pageScrollLocked = await page.evaluate(() => {
        const bodyOverflow = getComputedStyle(document.body).overflowY;
        const bodyPosition = getComputedStyle(document.body).position;
        return bodyOverflow === 'hidden' || bodyPosition === 'fixed';
      });
      expect(pageScrollLocked).toBe(true);

      const isFooterInsideDialog = await page.evaluate(() => {
        const dialog = document.querySelector('dialog[open]');
        const close = dialog?.querySelector('.btn[data-modal-close]');
        if (!dialog || !close) return false;

        const dialogBox = dialog.getBoundingClientRect();
        const closeBox = close.getBoundingClientRect();
        const hit = document.elementFromPoint(
          closeBox.left + closeBox.width / 2,
          closeBox.top + closeBox.height / 2,
        );

        return (
          closeBox.bottom <= dialogBox.bottom &&
          (hit === close || close.contains(hit))
        );
      });
      expect(isFooterInsideDialog).toBe(true);

      await footerClose.click();
      await expect(detailDialog).toBeHidden();
      await context.close();
    },
  );

  test('allows iOS touch scrolling inside long mobile session modal content', async ({ browser, browserName }) => {
    test.skip(browserName === 'firefox', 'Firefox does not support mobile emulation');
    const context = await browser.newContext({
      ...devices['iPhone 14 Pro'],
      baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8000',
    });
    await context.addInitScript(() => {
      Object.defineProperty(window.navigator, 'platform', { get: () => 'iPhone' });
      Object.defineProperty(window.navigator, 'maxTouchPoints', { get: () => 1 });
    });
    const page = await context.newPage();

    await page.goto('/chronology/event/autumn-open/');
    const sessionId = await page.locator('.session-card').nth(1).getAttribute('data-session-id');
    expect(sessionId).not.toBeNull();

    await page.evaluate((id) => {
      const description = document.querySelector(`#session-${id} [id^="info-"] div.leading-relaxed`);
      if (!description) throw new Error('Missing session description');
      description.innerHTML = Array.from(
        { length: 28 },
        (_, index) => `<p>Long mobile session description paragraph ${index + 1}.</p>`,
      ).join('');
    }, sessionId);

    await page.locator('.session-card').nth(1).getByRole('link').click();
    const detailDialog = page.getByRole('dialog', {
      name: 'Cozy Storytellers Circle',
    });
    await expect(detailDialog).toBeVisible();

    const mobileModalLayout = await page.evaluate(() => {
      const dialog = document.querySelector('dialog[open]');
      const tabContent = dialog?.querySelector('.tab-content');
      if (!(dialog instanceof HTMLElement) || !(tabContent instanceof HTMLElement)) return null;

      const dialogBox = dialog.getBoundingClientRect();
      const tabContentBox = tabContent.getBoundingClientRect();
      return {
        dialogHeight: dialogBox.height,
        tabContentHeight: tabContentBox.height,
        viewportHeight: window.innerHeight,
      };
    });
    expect(mobileModalLayout).not.toBeNull();
    expect(mobileModalLayout?.dialogHeight).toBeGreaterThan(
      mobileModalLayout?.viewportHeight * 0.75,
    );
    expect(mobileModalLayout?.tabContentHeight).toBeGreaterThan(240);

    const touchMoveAllowed = await page.evaluate(() => {
      const dialog = document.querySelector('dialog[open]');
      const activePanel = dialog?.querySelector('.tab-panel[data-active]');
      const text = activePanel?.querySelector('p');
      if (!dialog || !(activePanel instanceof HTMLElement) || !text) return false;

      const start = new Event('touchstart', { bubbles: true, cancelable: true });
      Object.defineProperties(start, {
        targetTouches: { value: [{ clientY: 300 }] },
        touches: { value: [{ clientY: 300 }] },
      });
      const move = new Event('touchmove', { bubbles: true, cancelable: true });
      Object.defineProperties(move, {
        targetTouches: { value: [{ clientY: 200 }] },
        touches: { value: [{ clientY: 200 }] },
      });

      text.dispatchEvent(start);
      text.dispatchEvent(move);

      return activePanel.scrollHeight > activePanel.clientHeight && !move.defaultPrevented;
    });
    expect(touchMoveAllowed).toBe(true);

    await detailDialog.getByRole('button', { name: 'Close' }).click();
    await expect(detailDialog).toBeHidden();
    await context.close();
  });
});
