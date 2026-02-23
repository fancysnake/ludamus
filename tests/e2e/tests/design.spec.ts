import { expect, test } from '@playwright/test';

test.describe('Design system page', () => {
  test('renders design showcase with component sections', async ({ page }) => {
    await page.goto('/design/');

    // Page should load (design.html extends base_tailwind)
    await expect(page).toHaveTitle(/design/i);

    // Should contain component examples — buttons, cards, alerts, etc.
    await expect(page.getByRole('button').first()).toBeVisible();

    await page.screenshot({
      path: 'test-results/design-page.png',
      fullPage: true,
    });
  });
});
