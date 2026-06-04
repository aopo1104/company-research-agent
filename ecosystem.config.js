module.exports = {
  apps: [
    {
      name: 'company-research-backend',
      script: 'application.py',
      interpreter: './.venv/Scripts/python.exe',
      cwd: './company-research-agent-main',
      env: {
        NODE_ENV: 'development'
      },
      autorestart: true,
      watch: ['backend', 'application.py'],
      ignore_watch: ['node_modules', '__pycache__', '.git', 'pdfs'],
      max_memory_restart: '500M',
      error_file: 'logs/backend-error.log',
      out_file: 'logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'company-research-frontend',
      script: 'npm',
      args: 'run dev',
      cwd: './company-research-agent-main/ui',
      autorestart: true,
      watch: ['src', 'public', 'package.json'],
      ignore_watch: ['node_modules', 'dist', '.git'],
      max_memory_restart: '300M',
      error_file: 'logs/frontend-error.log',
      out_file: 'logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
