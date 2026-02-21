import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const repoRoot = path.resolve(__dirname, '..', '..');

const loadEnv = (filePath: string) => {
  if (!fs.existsSync(filePath)) return;

  const content = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of content.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const [key, ...valueParts] = line.split('=');
    if (!key || process.env[key] !== undefined) continue;
    process.env[key] = valueParts.join('=');
  }
};

loadEnv(path.join(repoRoot, '.env'));
// We do not load .env.ci here. It's not meant for our end-to-end tests.

const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:8000`;

const WEB_COMMAND = 'mise boot-e2e';

export default defineConfig({
  testDir: './tests',
  outputDir: 'test-results',
  globalSetup: './global-setup.ts',
  /* Timeout per test */
  timeout: 120 * 1000,
  expect: {
    timeout: 10 * 1000,
  },
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 2 : undefined,
  /* Reporter to use */
  reporter: process.env.CI
    ? [['github'], ['html', { open: 'never' }]]
    : [['line'], ['html', { open: 'never' }]],
  /* Shared settings for all the projects below. */
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: process.env.CI ? 'retain-on-failure' : 'on-first-retry',
  },
  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['iPhone 14 Pro'] },
    },
  ],
  webServer: {
    command: WEB_COMMAND,
    url: BASE_URL,
    env: {
      ...process.env
    },
    reuseExistingServer: !process.env.CI,
    timeout: 180 * 1000,
    stdout: 'pipe',
    stderr: 'pipe',
    cwd: repoRoot,
  },
});
