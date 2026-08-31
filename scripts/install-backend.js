const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const isWin = process.platform === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');
const venvDir = path.join(backendDir, 'venv');
const venvPython = path.join(venvDir, isWin ? 'Scripts\\python.exe' : 'bin/python');
const venvPip = path.join(venvDir, isWin ? 'Scripts\\pip.exe' : 'bin/pip');

function findSystemPython() {
  const candidates = isWin ? ['python', 'python3'] : ['python3', 'python'];
  for (const cmd of candidates) {
    const check = spawnSync(isWin ? 'where' : 'which', [cmd], { stdio: 'pipe' });
    if (check.status === 0 && check.stdout.toString().trim()) {
      return cmd;
    }
  }
  throw new Error('No python/python3 found on PATH. Please install Python.');
}

if (fs.existsSync(venvPython)) {
  console.log('Backend venv already exists, skipping install.');
  process.exit(0);
}

console.log('Creating backend virtual environment...');
const python = findSystemPython();
const create = spawnSync(python, ['-m', 'venv', 'venv'], { cwd: backendDir, stdio: 'inherit' });
if (create.status !== 0) {
  console.error('Failed to create venv');
  process.exit(1);
}

console.log('Installing backend requirements...');
const install = spawnSync(venvPip, ['install', '-r', 'requirements.txt'], { cwd: backendDir, stdio: 'inherit' });
process.exit(install.status ?? 0);
