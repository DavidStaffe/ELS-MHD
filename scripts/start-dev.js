#!/usr/bin/env node

const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const rootDir = path.resolve(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');
const frontendDir = path.join(rootDir, 'frontend');

const backendPortStart = Number(process.env.BACKEND_PORT || '8000');
const frontendPortStart = Number(process.env.FRONTEND_PORT || '3000');
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';

const venvPython =
  process.platform === 'win32'
    ? path.join(backendDir, '.venv', 'Scripts', 'python.exe')
    : path.join(backendDir, '.venv', 'bin', 'python');

const backendPython =
  process.env.BACKEND_PYTHON ||
  (fs.existsSync(venvPython) ? venvPython : 'python3');

let shuttingDown = false;
let exitCode = 0;
const children = [];

function log(msg) {
  console.log(`[dev] ${msg}`);
}

function warn(msg) {
  console.warn(`[dev] ${msg}`);
}

function isPortFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.on('error', () => resolve(false));
    server.listen(port, () => {
      server.close(() => resolve(true));
    });
  });
}

async function findFreePort(startPort, maxAttempts = 50) {
  for (let port = startPort; port < startPort + maxAttempts; port += 1) {
    // eslint-disable-next-line no-await-in-loop
    if (await isPortFree(port)) return port;
  }
  throw new Error(
    `No free port found in range ${startPort}-${startPort + maxAttempts - 1}`,
  );
}

function stopChildren() {
  if (shuttingDown) return;
  shuttingDown = true;
  log('Stopping backend and frontend ...');
  for (const child of children) {
    if (!child.killed) {
      child.kill('SIGTERM');
    }
  }
  setTimeout(() => {
    for (const child of children) {
      if (!child.killed) {
        child.kill('SIGKILL');
      }
    }
  }, 5000).unref();
}

function maybeExit() {
  if (!shuttingDown) return;
  const allClosed = children.every(
    (child) => child.exitCode !== null || child.signalCode !== null,
  );
  if (allClosed) {
    process.exit(exitCode);
  }
}

function startProcess(name, command, args, cwd, env = {}) {
  log(`Starting ${name} ...`);
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: 'inherit',
  });

  child.on('error', (err) => {
    warn(`${name} failed to start: ${err.message}`);
    exitCode = 1;
    stopChildren();
    maybeExit();
  });

  child.on('exit', (code, signal) => {
    if (!shuttingDown) {
      if (code !== 0) {
        warn(`${name} exited with code ${code}`);
        exitCode = code || 1;
      } else if (signal) {
        warn(`${name} stopped by signal ${signal}`);
        exitCode = 1;
      }
      stopChildren();
    }
    maybeExit();
  });

  children.push(child);
  return child;
}

function localFrontendOrigins(port) {
  const origins = new Set([
    `http://localhost:${port}`,
    `http://127.0.0.1:${port}`,
  ]);

  const interfaces = os.networkInterfaces();
  for (const infos of Object.values(interfaces)) {
    for (const info of infos || []) {
      if (!info || info.internal) continue;
      if (info.family !== 'IPv4') continue;
      origins.add(`http://${info.address}:${port}`);
    }
  }

  return origins;
}

async function main() {
  if (!fs.existsSync(path.join(backendDir, '.env'))) {
    warn(
      'backend/.env not found. Create it before running if backend startup fails.',
    );
  }

  const backendPort = await findFreePort(backendPortStart);
  const frontendPort = await findFreePort(frontendPortStart);

  if (backendPort !== backendPortStart) {
    warn(
      `Backend port ${backendPortStart} in use; falling back to ${backendPort}.`,
    );
  }
  if (frontendPort !== frontendPortStart) {
    warn(
      `Frontend port ${frontendPortStart} in use; falling back to ${frontendPort}.`,
    );
  }

  const existingCors = (process.env.CORS_ORIGINS || '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
  const corsSet = new Set(existingCors);
  for (const origin of localFrontendOrigins(frontendPort)) {
    corsSet.add(origin);
  }
  const corsOrigins = Array.from(corsSet).join(',');

  log(`Using backend python: ${backendPython}`);
  log(`Backend URL expected at: http://localhost:${backendPort}`);
  log(`Frontend URL expected at: http://localhost:${frontendPort}`);

  startProcess(
    'backend',
    backendPython,
    [
      '-m',
      'uvicorn',
      'server:app',
      '--reload',
      '--host',
      '0.0.0.0',
      '--port',
      String(backendPort),
    ],
    backendDir,
    {
      CORS_ORIGINS: corsOrigins,
    },
  );

  startProcess('frontend', npmCmd, ['start'], frontendDir, {
    ...(process.env.REACT_APP_BACKEND_URL
      ? { REACT_APP_BACKEND_URL: process.env.REACT_APP_BACKEND_URL }
      : {}),
    REACT_APP_BACKEND_PORT: String(backendPort),
    PORT: String(frontendPort),
  });
}

main().catch((err) => {
  warn(`Startup failed: ${err.message}`);
  process.exit(1);
});

process.on('SIGINT', () => {
  exitCode = 0;
  stopChildren();
  maybeExit();
});

process.on('SIGTERM', () => {
  exitCode = 0;
  stopChildren();
  maybeExit();
});
