const { spawn, spawnSync } = require('child_process');
const path = require('path');

const isWin = process.platform === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');
const venvPython = path.join(backendDir, isWin ? 'venv\\Scripts\\python.exe' : 'venv/bin/python');

console.log('Running database migrations...');
const migrate = spawnSync(venvPython, ['-m', 'alembic', 'upgrade', 'head'], {
  cwd: backendDir,
  stdio: 'inherit',
});
if (migrate.status !== 0) {
  console.error('Migration failed, starting server anyway...');
}

console.log('Starting backend...');
const child = spawn(venvPython, ['-m', 'uvicorn', 'app.main:app', '--reload', '--host', '0.0.0.0', '--port', '8000'], {
  cwd: backendDir,
  stdio: 'inherit',
});

child.on('close', (code) => process.exit(code ?? 0));
