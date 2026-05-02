import { expect, test } from '@playwright/test';

// Tiny 1x1 PNG, identical to PNG_BYTES used in integration tests.
const PNG_BYTES = Buffer.from(
  '89504e470d0a1a0a0000000d4948445200000001000000010802000000' +
    '907753de0000000c49444154789c63606060000000040001f6173855' +
    '0000000049454e44ae426082',
  'hex',
);

// Tiny 1x1 GIF — used to assert that GIF uploads are rejected.
const GIF_BYTES = Buffer.from(
  '47494638376101000100810000ffffff000000000000000000' +
    '2c000000000100010000080400010404003b',
  'hex',
);

test.describe('Event cover image upload', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin/login/');
    await page.getByLabel('Username:').fill('e2e-manager');
    await page.getByLabel('Password:').fill('e2e-manager-123');
    await page.getByRole('button', { name: /Log in/i }).click();
  });

  test('manager uploads cover image via event settings', async ({ page }) => {
    await page.goto('/panel/event/autumn-open/settings/');

    // Preview is hidden initially when there's no cover yet.
    const preview = page.locator('#cover-image-preview');
    await expect(preview).toBeHidden();

    await page.locator('#id_cover_image').setInputFiles({
      name: 'cover.png',
      mimeType: 'image/png',
      buffer: PNG_BYTES,
    });

    // Client-side preview becomes visible immediately, before submit.
    await expect(preview).toBeVisible();
    await expect(preview).toHaveAttribute('src', /^blob:/);

    await page.getByRole('button', { name: 'Save Settings' }).click();

    await expect(
      page.getByText('Event settings saved successfully.'),
    ).toBeVisible();

    // After save, the saved cover persists across navigation.
    await page.goto('/panel/event/autumn-open/settings/');
    const persisted = page.locator('#cover-image-preview');
    await expect(persisted).toBeVisible();
    await expect(persisted).toHaveAttribute('src', /\/media\/events\//);
  });

  test('rejects cover image larger than 2 MB', async ({ page }) => {
    await page.goto('/panel/event/autumn-open/settings/');

    // Pad valid PNG so the upload reaches size validation, not image parsing.
    const oversize = Buffer.concat([
      PNG_BYTES,
      Buffer.alloc(2 * 1024 * 1024 + 1, 0),
    ]);
    await page.locator('#id_cover_image').setInputFiles({
      name: 'huge.png',
      mimeType: 'image/png',
      buffer: oversize,
    });

    await page.getByRole('button', { name: 'Save Settings' }).click();

    await expect(page.getByText(/Image too large/i)).toBeVisible();
  });

  test('rejects unsupported (GIF) image format', async ({ page }) => {
    await page.goto('/panel/event/autumn-open/settings/');

    // The file picker advertises restricted MIME types via `accept` —
    // verify the contract is in the DOM so we know the browser hint matches
    // the server-side restriction.
    await expect(page.locator('#id_cover_image')).toHaveAttribute(
      'accept',
      'image/jpeg,image/png,image/webp,image/avif',
    );

    await page.locator('#id_cover_image').setInputFiles({
      name: 'cover.gif',
      mimeType: 'image/gif',
      buffer: GIF_BYTES,
    });

    await page.getByRole('button', { name: 'Save Settings' }).click();

    await expect(
      page.getByText(/Unsupported image format/i),
    ).toBeVisible();
  });
});
