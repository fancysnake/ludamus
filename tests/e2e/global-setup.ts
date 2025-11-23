import { execSync } from 'node:child_process';
import path from 'node:path';
import type { FullConfig } from '@playwright/test';

const repoRoot = path.resolve(__dirname, '..', '..');

export default async function globalSetup(_config: FullConfig) {
  const scriptPath = path.relative(repoRoot, path.resolve(__dirname, 'scripts', 'bootstrap_data.py'));
  const useDocker = process.env.CI !== 'true';
  const command = useDocker
    ? `docker compose run --rm -T web python /app/${scriptPath}`
    : `poetry run python ${scriptPath}`;
  execSync(command, {
    cwd: repoRoot,
    stdio: 'inherit',
    env: {
      ...process.env,
    },
  });
}
