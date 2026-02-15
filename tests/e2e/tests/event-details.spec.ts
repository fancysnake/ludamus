import { expect, test } from '@playwright/test';

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
    await expect(megaStrategyCard).toContainText('Convention Center ›');
    await expect(megaStrategyCard).toContainText('Main Hall ›');
    await expect(megaStrategyCard).toContainText('East Wing');
    await megaStrategyCard.click();

    const detailDialog = page.getByRole('dialog', { name: 'Mega Strategy Lab' });
    await expect(detailDialog).toBeVisible();
    await expect(detailDialog).toContainText('Alex Morgan');

    await detailDialog.getByRole('button', { name: 'Close' }).first().click();
    await expect(detailDialog).toBeHidden();
  });
});
