@echo off
cd /d %~dp0
echo [1/3] 拉取最新代码...
git pull
echo [2/3] 构建前端...
cd ui
call npm run build
cd ..
echo [3/3] 重启后端...
pm2 restart ecosystem.config.js
echo.
echo ========================================
echo   部署完成！
echo   前端: https://www.jimmydean.top/companyResearch/
echo   后端: PM2 管理 (pm2 status)
echo ========================================
pause
