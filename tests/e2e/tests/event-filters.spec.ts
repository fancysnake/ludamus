import { expect, test } from '@playwright/test';

const MOBILE_WIDTH = 375;

test.describe('Event filter panel', () => {
  test('filter panel does not overflow viewport on mobile', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: MOBILE_WIDTH, height: 812 },
    });
    const page = await context.newPage();

    await page.goto('/chronology/event/autumn-open/');
    await page.locator('#filter-toggle').click();
    await expect(page.locator('#filter-panel.is-open')).toBeVisible();

    const box = await page.locator('#filter-panel').boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(MOBILE_WIDTH);

    await context.close();
  });
});
