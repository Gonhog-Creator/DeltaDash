const { spawn } = require('child_process');
const path = require('path');

const isWin = process.platform === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');
const venvPython = path.join(backendDir, isWin ? 'venv\\Scripts\\python.exe' : 'venv/bin/python');

const child = spawn(venvPython, ['-m', 'alembic', 'upgrade', 'head'], {
  cwd: backendDir,
  stdio: 'inherit',
});

child.on('close', (code) => process.exit(code ?? 0));
