# 开发工作流

## 启动开发环境

### 后端

```powershell
cd d:\PythonProject\company-research-agent-main\company-research-agent-main
python application.py
# → Uvicorn 启动于 http://0.0.0.0:9999
```

### 前端

```powershell
cd ui
npm run dev
# → Vite 启动于 http://localhost:3004
```

### 常见问题

**端口 9999 被占用**：
```powershell
Get-NetTCPConnection -LocalPort 9999 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## 开发流程

### 修改 Prompt

1. 编辑 `backend/prompt_templates/` 下对应文件
2. 无需重启后端（模块级变量在导入时求值，但 FastAPI 热重载会刷新）
3. 验证导入：`python -c "from backend.prompt_templates.XXX import YYY; print('OK')"`
4. 运行一次研究验证输出质量

### 修改管道逻辑

1. 编辑对应 node 文件
2. 重启后端
3. 通过 UI 或 curl 触发研究验证

### 修改前端

1. Vite HMR 自动热更新
2. 如果修改 `types/index.ts`，确保与后端 State 一致

## 测试研究流程

### 通过 UI

1. 打开 http://localhost:3004
2. 输入目标公司 URL（如 `https://www.example.com`）
3. 点击开始研究
4. 观察实时进度和最终报告

### 通过 curl

```bash
# 启动研究
curl -X POST http://localhost:9999/research \
  -H "Content-Type: application/json" \
  -d '{"company_url": "https://www.example.com"}'
# 返回 {"job_id": "xxx"}

# 获取报告
curl http://localhost:9999/research/xxx/report
```

## Git 工作流

- 主分支：`main`
- 功能开发：`feature/xxx` 分支
- Commit message：中文简短描述
- 无 CI/CD（TODO：添加 GitHub Actions）
