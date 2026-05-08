import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

const expectPageScrollLocked = async (page: Page) => {
  const pageScrollLocked = await page.evaluate(() => {
    const bodyOverflow = getComputedStyle(document.body).overflowY;
    const bodyPosition = getComputedStyle(document.body).position;
    return bodyOverflow === 'hidden' || bodyPosition === 'fixed';
  });
  expect(pageScrollLocked).toBe(true);
};

test.describe('Modal surfaces using page scroll lock', () => {
  test('opens and closes the pending proposal review modal', async ({ browser }) => {
    const context = await browser.newContext({
      storageState: path.join(__dirname, '..', '.auth-state-superuser.json'),
    });
    const page = await context.newPage();

    await page.goto('/chronology/event/autumn-open/');

    await page
      .getByRole('row')
      .filter({ hasText: 'Pending Neon Proposal' })
      .getByRole('link', { name: /Review/ })
      .click();

    const dialog = page.getByRole('dialog', { name: 'Pending Neon Proposal' });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Proposal review modal content used by e2e tests.');
    await expectPageScrollLocked(page);

    await dialog.getByRole('button', { name: 'Close' }).click();
    await expect(dialog).toBeHidden();

    await context.close();
  });
});
