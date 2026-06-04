const path = require('path');

const ROOT = __dirname;

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
    }
  ]
};
