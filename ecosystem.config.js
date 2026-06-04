const path = require('path');

const ROOT = __dirname;
const NPM_CMD = process.platform === 'win32' ? 'npm.cmd' : 'npm';

module.exports = {
  apps: [
    {
      name: 'company-research-backend',
      script: path.join(ROOT, '.venv', 'Scripts', 'python.exe'),
      args: 'application.py',
      cwd: ROOT,
      windowsHide: true,
      env: {
        NODE_ENV: 'development'
      },
      autorestart: true,
      watch: ['backend', 'application.py'],
      ignore_watch: ['node_modules', '__pycache__', '.git', 'pdfs'],
      max_memory_restart: '500M',
      error_file: path.join(ROOT, 'logs', 'backend-error.log'),
      out_file: path.join(ROOT, 'logs', 'backend-out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'company-research-frontend',
      script: NPM_CMD,
      args: 'run dev',
      interpreter: 'none',
      windowsHide: true,
      cwd: path.join(ROOT, 'ui'),
      autorestart: true,
      watch: ['src', 'public', 'package.json'],
      ignore_watch: ['node_modules', 'dist', '.git'],
      max_memory_restart: '300M',
      error_file: path.join(ROOT, 'logs', 'frontend-error.log'),
      out_file: path.join(ROOT, 'logs', 'frontend-out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
