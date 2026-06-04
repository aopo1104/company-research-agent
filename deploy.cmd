@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo.
echo ========================================
echo   部署开始...
echo ========================================
echo.

echo [1/3] 拉取最新代码...
git pull
if errorlevel 1 (
  echo [错误] Git 拉取失败！
  pause
  exit /b 1
)

echo [2/3] 构建前端...
cd ui
echo 安装依赖...
call npm install
if errorlevel 1 (
  echo [错误] npm install 失败！
  cd ..
  pause
  exit /b 1
)
echo 构建项目...
call npm run build
if errorlevel 1 (
  echo [错误] npm run build 失败！
  cd ..
  pause
  exit /b 1
)
cd ..

echo [3/3] 重启后端...
pm2 restart ecosystem.config.js
if errorlevel 1 (
  echo [警告] PM2 重启可能失败，检查 PM2 状态...
)

echo.
echo ========================================
echo   部署完成！
echo ========================================
echo.
echo 检查服务状态：
pm2 status
echo.
echo 查看后端日志：
echo   pm2 logs company-research-backend
echo.
echo 访问前端：
echo   https://www.jimmydean.top/companyResearch/
echo.
pause
