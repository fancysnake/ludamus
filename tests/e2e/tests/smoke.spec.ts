import { test } from '@playwright/test';

// Entire suite stays skipped until real scenarios are implemented.
test.describe('Ludamus smoke suite', () => {
  test.skip(true, 'The real smoke tests will be implemented in upcoming tasks.');

  test('placeholder', async () => {
    // Intentionally left blank.
  });
});
