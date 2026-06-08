---
description: "实现一个新功能或任务"
---

# 实现任务

## 上下文

**任务描述**：{{task_description}}
**涉及模块**：{{module}}

## 执行步骤

1. 先阅读相关现有代码，理解上下文
2. 确认修改范围（列出要改动的文件）
3. 实现功能
4. 验证：启动后端 `python application.py`，检查无报错

## 约束

- 检查 `seller_profile.py` 是否需要添加新配置
- 如果涉及 prompt 修改，确保 f-string 中模板变量用 `{{var}}` 双转义
- 如果修改了 State 类型，同步更新前端 `types/index.ts`
- 如果新增 API 端点，同步更新 `api.instructions.md` 的端点列表

## 验证清单

- [ ] `python -c "from backend.prompt_templates import ..."` 无 ImportError
- [ ] 后端启动无报错
- [ ] 前端（如涉及）无 TS 编译错误
