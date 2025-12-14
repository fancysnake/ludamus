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

// Load .env first (local dev), then .env.ci as fallback (CI)
// loadEnv skips already-set variables, so .env.ci takes precedence
loadEnv(path.join(repoRoot, '.env.ci'));
loadEnv(path.join(repoRoot, '.env'));

const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:8000`;

export default defineConfig({
  testDir: './tests',
  outputDir: 'test-results',
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
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: [
    {
      command: 'poetry run poe e2e-mock-auth0',
      url: 'http://localhost:9999/.well-known/openid-configuration',
      reuseExistingServer: process.env.E2E_REUSE_SERVER === 'true',
      timeout: 10 * 1000,
      stdout: 'pipe',
      stderr: 'pipe',
      cwd: repoRoot,
    },
    {
      command: 'poetry run poe e2e-setup && poetry run poe e2e-start',
      url: BASE_URL,
      env: {
        ...process.env,
        DJANGO_SETTINGS_MODULE: process.env.DJANGO_SETTINGS_MODULE!,
        PYTHONPATH: process.env.PYTHONPATH!,
      },
      reuseExistingServer: process.env.E2E_REUSE_SERVER === 'true',
      timeout: 180 * 1000,
      stdout: 'pipe',
      stderr: 'pipe',
      cwd: repoRoot,
    },
  ],
});
