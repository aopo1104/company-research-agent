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
      script: 'cmd',
      args: '/c npm.cmd run build',
      interpreter: 'none',
      windowsHide: true,
      cwd: path.join(ROOT, 'ui'),
      autorestart: false,
      watch: false,
      error_file: path.join(ROOT, 'logs', 'frontend-build.log'),
      out_file: path.join(ROOT, 'logs', 'frontend-build.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
