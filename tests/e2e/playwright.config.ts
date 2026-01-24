import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const repoRoot = path.resolve(__dirname, '..', '..');

// Ensure Django can find settings and source modules when Playwright spawns
// helper processes (global setup and the webServer command) on CI, where the
// environment is otherwise bare.
process.env.DJANGO_SETTINGS_MODULE ||= 'ludamus.config.settings';
process.env.PYTHONPATH ||= path.join(repoRoot, 'src');

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

const WEB_COMMAND = process.env.CI
  ? 'poetry run sh -c "django-admin migrate --noinput && django-admin createcachetable && django-admin downloadvendor && python tests/e2e/scripts/bootstrap_data.py && django-admin runserver --insecure 0.0.0.0:8000"'
  : 'docker compose up';

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
      ...process.env,
      DJANGO_SETTINGS_MODULE: process.env.DJANGO_SETTINGS_MODULE!,
      PYTHONPATH: process.env.PYTHONPATH!,
      DEBUG: "false"
    },
    reuseExistingServer: !process.env.CI,
    timeout: 180 * 1000,
    stdout: 'pipe',
    stderr: 'pipe',
    cwd: repoRoot,
  },
});
