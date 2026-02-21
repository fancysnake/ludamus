import { execSync } from 'node:child_process';
import path from 'node:path';
import type { FullConfig } from '@playwright/test';

const repoRoot = path.resolve(__dirname, '..', '..');
const scriptPath = path.join('tests', 'e2e', 'scripts', 'bootstrap_data.py');

const baseEnv = {
  ...process.env,
};

const run = (command: string) =>
  execSync(command, {
    cwd: repoRoot,
    stdio: 'inherit',
    env: baseEnv,
  });

export default async function globalSetup(_config: FullConfig) {
  run('mise run dj migrate --noinput');
  run('mise run dj createcachetable');
  run('mise run dj downloadvendor');
  run(`mise run p run python ${scriptPath}`);
  run('mise run build-frontend');
}
