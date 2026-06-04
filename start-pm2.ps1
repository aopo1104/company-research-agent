# ============================================================
# start-pm2.ps1 — 一键启动 company-research-agent (PM2)
# 用法：在项目根目录执行  .\start-pm2.ps1
# ============================================================

$ROOT = $PSScriptRoot

# ── 1. 创建 logs 目录 ──────────────────────────────────────
$logsDir = Join-Path $ROOT "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
    Write-Host "[OK] 已创建 logs 目录"
}

# ── 2. 写入 ecosystem.config.js（始终覆盖，确保最新）──────
$ecosystemPath = Join-Path $ROOT "ecosystem.config.js"
$ecosystemContent = @"
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
      args: '/c npm.cmd run dev',
      interpreter: 'none',
      windowsHide: true,
      cwd: path.join(ROOT, 'ui'),
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      error_file: path.join(ROOT, 'logs', 'frontend-error.log'),
      out_file: path.join(ROOT, 'logs', 'frontend-out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
"@

[System.IO.File]::WriteAllText($ecosystemPath, $ecosystemContent, [System.Text.Encoding]::UTF8)
Write-Host "[OK] ecosystem.config.js 已写入"

# ── 3. 检查 .venv ──────────────────────────────────────────
$venvPython = Join-Path $ROOT ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[警告] 未找到 .venv，正在创建虚拟环境..."
    python -m venv (Join-Path $ROOT ".venv")
    & (Join-Path $ROOT ".venv\Scripts\pip.exe") install -r (Join-Path $ROOT "requirements.txt") -i https://mirrors.aliyun.com/pypi/simple/
    Write-Host "[OK] 虚拟环境已创建并安装依赖"
}

# ── 4. 检查前端 node_modules ───────────────────────────────
$uiModules = Join-Path $ROOT "ui\node_modules"
if (-not (Test-Path $uiModules)) {
    Write-Host "[警告] ui/node_modules 不存在，正在安装前端依赖..."
    Push-Location (Join-Path $ROOT "ui")
    npm install
    Pop-Location
    Write-Host "[OK] 前端依赖已安装"
}

# ── 5. 停止旧进程，启动新进程 ──────────────────────────────
Write-Host ""
Write-Host "正在重启 PM2 进程..."
pm2 delete company-research-backend 2>$null
pm2 delete company-research-frontend 2>$null
pm2 start $ecosystemPath
pm2 save

# ── 6. 显示状态 ────────────────────────────────────────────
Write-Host ""
pm2 status
Write-Host ""
Write-Host "============================================"
Write-Host "  前端: http://localhost:3004/companyResearch/"
Write-Host "  后端: http://localhost:9999"
Write-Host "  日志: pm2 logs"
Write-Host "============================================"
