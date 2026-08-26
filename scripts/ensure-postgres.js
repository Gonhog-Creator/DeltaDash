const { execSync, spawn } = require('child_process');
const { existsSync } = require('fs');

const DOCKER_DESKTOP_PATH = 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe';
const MAX_WAIT_DOCKER = 60; // seconds
const MAX_WAIT_POSTGRES = 30; // seconds

function run(cmd, opts = {}) {
  return execSync(cmd, { stdio: 'pipe', encoding: 'utf8', ...opts }).trim();
}

function sleepSync(ms) {
  const buf = new Int32Array(new SharedArrayBuffer(4));
  Atomics.wait(buf, 0, 0, ms);
}

function isDockerRunning() {
  try {
    run('docker info');
    return true;
  } catch {
    return false;
  }
}

function startDockerDesktop() {
  if (!existsSync(DOCKER_DESKTOP_PATH)) {
    console.error('Docker Desktop not found at:', DOCKER_DESKTOP_PATH);
    console.error('Please start Docker Desktop manually, then run "npm run dev" again.');
    process.exit(1);
  }
  console.log('Starting Docker Desktop...');
  spawn('cmd', ['/c', `"${DOCKER_DESKTOP_PATH}"`], { shell: true, detached: true, stdio: 'ignore' });
}

function waitForDocker() {
  console.log('Waiting for Docker daemon to be ready...');
  for (let i = 0; i < MAX_WAIT_DOCKER; i++) {
    if (isDockerRunning()) {
      console.log('Docker daemon is ready.');
      return true;
    }
    process.stdout.write('.');
    sleepSync(1000);
  }
  console.error('\nDocker daemon did not become ready in time. Please start Docker Desktop manually.');
  process.exit(1);
}

function isPostgresRunning() {
  try {
    const output = run('docker compose ps --format json postgres');
    if (!output) return false;
    const lines = output.split('\n').filter(Boolean);
    for (const line of lines) {
      try {
        const data = JSON.parse(line);
        if (data.State === 'running') return true;
      } catch {
        // not JSON, try plain text
        if (line.includes('Up')) return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}

function startPostgres() {
  console.log('Starting postgres container...');
  try {
    execSync('docker compose up -d postgres', { stdio: 'inherit' });
  } catch {
    console.error('Failed to start postgres. Check your docker-compose.yml.');
    process.exit(1);
  }
}

function waitForPostgres() {
  console.log('Waiting for postgres to be ready...');
  for (let i = 0; i < MAX_WAIT_POSTGRES; i++) {
    try {
      run('docker compose exec -T postgres pg_isready -U ballistic_user -d ballistic');
      console.log('\nPostgres is ready.');
      return true;
    } catch {
      process.stdout.write('.');
      sleepSync(1000);
    }
  }
  console.error('\nPostgres did not become ready in time.');
  process.exit(1);
}

function main() {
  // Step 1: Ensure Docker daemon is running
  if (!isDockerRunning()) {
    startDockerDesktop();
    waitForDocker();
  } else {
    console.log('Docker daemon is already running.');
  }

  // Step 2: Ensure postgres container is running
  if (!isPostgresRunning()) {
    startPostgres();
    waitForPostgres();
  } else {
    console.log('Postgres container is already running.');
  }

  console.log('Database is ready. Starting dev servers...\n');
}

main();
