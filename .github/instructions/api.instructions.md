---
applyTo: "application.py"
---

# API 开发规则

## 端点列表

| 路径 | 方法 | 用途 |
|------|------|------|
| `/` | GET | 健康检查 |
| `/research` | POST | 启动全流程研究，返回 job_id |
| `/research/{job_id}/stream` | GET | SSE 事件流（实时进度 + 最终报告） |
| `/research/{job_id}/report` | GET | 轮询获取已完成报告 |
| `/research-quick` | POST | 快速研究（单次搜索 + 单次 LLM） |
| `/extract-company-info` | POST | 从 URL 提取公司名/行业/地点 |
| `/generate-email` | POST | 基于报告生成 B2B 开发信 |
| `/generate-pdf` | POST | Markdown → PDF |
| `/translate` | POST | 翻译报告 |

## SSE 事件格式

```
event: research_init
data: {"job_id": "...", "company": "..."}

event: progress
data: {"node": "company_researcher", "status": "complete", ...}

event: scrape_source
data: {"url": "...", "status": "success", "method": "static", "chars": 12000}

event: complete
data: {"report": "# 报告标题\n\n...", "references": [...]}
```

## 规则

1. SSE 流每 15s 发送 `: keepalive` 注释防止代理超时
2. 新增端点时保持与现有命名风格一致（`/resource` 或 `/action-noun`）
3. 请求体验证使用 Pydantic model 或 TypedDict
4. 错误响应统一使用 `{"error": "message"}` 格式
5. 长任务不阻塞主线程，使用 `asyncio.create_task` 放入后台
