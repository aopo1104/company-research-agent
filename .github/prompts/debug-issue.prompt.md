---
description: "调试一个问题"
---

# 调试问题

## 问题描述

**现象**：{{symptom}}
**错误信息**：{{error_message}}
**涉及文件**：{{file}}

## 调试流程

### 1. 常见问题快速排查

| 症状 | 常见原因 |
|------|----------|
| NameError: `company` | f-string 中 `{company}` 没有转义为 `{{company}}` |
| Port 9999 占用 | 旧 Python 进程未退出，执行 `Get-NetTCPConnection -LocalPort 9999 \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` |
| ImportError | `__init__.py` 缺少 re-export，或 circular import |
| 报告缺少章节 | 检查 Editor COMPILE_CONTENT_PROMPT 中对应 section 是否存在 |
| 合作分析为空 | 检查 briefing 数据是否传入 Editor，seller_profile 是否导入正确 |
| 403/超时大量出现 | 检查 DomainCircuitBreaker 是否正确触发 |

### 2. 诊断步骤

1. 确认错误发生的管道阶段（看 SSE progress 事件的 node 名）
2. 在对应 node 文件添加 `logger.debug(...)` 临时日志
3. 重新运行，观察日志
4. 修复后移除调试日志

### 3. 验证

- 修复后执行一次完整研究流程确认无回归
- 检查修复是否影响其他阶段的输入/输出
