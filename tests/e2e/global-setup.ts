import { execSync } from 'node:child_process';
import path from 'node:path';
import type { FullConfig } from '@playwright/test';

const repoRoot = path.resolve(__dirname, '..', '..');

const baseEnv = {
  ...process.env,
  DJANGO_SETTINGS_MODULE: process.env.DJANGO_SETTINGS_MODULE ?? 'ludamus.config.settings',
  PYTHONPATH: process.env.PYTHONPATH ?? path.join(repoRoot, 'src'),
};

const run = (command: string) =>
  execSync(command, {
    cwd: repoRoot,
    stdio: 'inherit',
    env: baseEnv,
  });

export default async function globalSetup(_config: FullConfig) {
  if (process.env.E2E_SKIP_SETUP === 'true') {
    console.log('Skipping E2E setup (E2E_SKIP_SETUP=true)');
    return;
  }

  run('poetry run poe e2e-setup');
}
