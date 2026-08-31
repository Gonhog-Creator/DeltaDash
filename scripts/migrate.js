const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const isWin = process.platform === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');
const venvPython = path.join(backendDir, isWin ? 'venv\\Scripts\\python.exe' : 'venv/bin/python');

function findInterpreter() {
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }

  const candidates = isWin ? ['python', 'python3'] : ['python3', 'python'];
  for (const cmd of candidates) {
    const check = spawnSync(isWin ? 'where' : 'which', [cmd], { stdio: 'pipe' });
    if (check.status === 0 && check.stdout.toString().trim()) {
      console.log(`No venv found, falling back to system interpreter: ${cmd}`);
      return cmd;
    }
  }

  throw new Error('Could not find a Python interpreter.');
}

const python = findInterpreter();

const child = spawn(python, ['-m', 'alembic', 'upgrade', 'head'], {
  cwd: backendDir,
  stdio: 'inherit',
});

child.on('close', (code) => process.exit(code ?? 0));
