import { execSync } from 'node:child_process';
import path from 'node:path';
import type { FullConfig } from '@playwright/test';

const repoRoot = path.resolve(__dirname, '..', '..');
const scriptPath = path.join('tests', 'e2e', 'scripts', 'bootstrap_data.py');

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
  const useDocker = process.env.CI !== 'true';

  if (useDocker) {
    run(
      'docker compose run --rm -T web sh -c "cd src && django-admin migrate --noinput && django-admin createcachetable && python /app/tests/e2e/scripts/bootstrap_data.py"',
    );
    return;
  }

  run('poetry run django-admin migrate --noinput');
  run('poetry run django-admin createcachetable');
  run(`poetry run python ${scriptPath}`);
}
