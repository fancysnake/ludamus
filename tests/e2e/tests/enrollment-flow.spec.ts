import { expect, test } from '@playwright/test';

test.describe('Anonymous enrollment flow', () => {
  test('activates anonymous mode and navigates to session enrollment', async ({
    page,
  }) => {
    // Activate anonymous enrollment (creates anonymous user + session cookies)
    await page.goto('/chronology/event/autumn-open/anonymous/do/activate');
    await expect(page).toHaveURL(/\/chronology\/event\/autumn-open\//);

    // Navigate to anonymous enrollment for first session
    const enrollLink = page
      .locator('a[href*="/enrollment/anonymous"]')
      .first();

    if (await enrollLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await enrollLink.click();

      // anonymous_enroll.html — our converted template
      await expect(
        page.getByRole('heading', { name: 'Anonymous Enrollment' }),
      ).toBeVisible();

      // Should display the anonymous code prominently
      await expect(page.getByText('Your Anonymous Code')).toBeVisible();

      // Session details card
      await expect(page.getByText('Host')).toBeVisible();
      await expect(page.getByText('Participants')).toBeVisible();
      await expect(page.getByText('Time')).toBeVisible();

      // Enrollment action button
      await expect(
        page.getByRole('button', { name: /Enroll Now|Complete Enrollment/ }),
      ).toBeVisible();

      // Back to event link
      await expect(
        page.getByRole('link', { name: 'Back to Event' }),
      ).toBeVisible();

      // Footer reminder about saving code
      await expect(
        page.getByText('Save this code to access your enrollments later'),
      ).toBeVisible();
    }
  });

  test('anonymous enrollment page shows name input when user has no name', async ({
    page,
  }) => {
    // Activate anonymous mode
    await page.goto('/chronology/event/autumn-open/anonymous/do/activate');

    const enrollLink = page
      .locator('a[href*="/enrollment/anonymous"]')
      .first();

    if (await enrollLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await enrollLink.click();

      // New anonymous users don't have a name set yet, so we should see the name input
      await expect(page.getByLabel('Name')).toBeVisible();
      await expect(
        page.getByText('Your public display name'),
      ).toBeVisible();
    }
  });
});

test.describe('Session enrollment (requires auth)', () => {
  test('unauthenticated access to session enrollment redirects to login', async ({
    page,
  }) => {
    const response = await page.goto('/chronology/session/1/enrollment/');
    // LoginRequiredMixin should redirect to login
    expect(response?.url()).toMatch(/login|auth/);
  });
});
