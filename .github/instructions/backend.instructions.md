---
applyTo: "backend/**,application.py"
---

# 后端开发规则

## 架构

LangGraph StateGraph 8 阶段管道：

```
Grounding → [Company|Industry|Financial|News|SocialMedia] (并行)
         → Collector → Curator → Enricher → Briefing → Editor
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `application.py` | FastAPI 路由、SSE 流、任务调度 |
| `backend/graph.py` | LangGraph 图定义、节点连接 |
| `backend/classes/state.py` | 状态定义、全局 job_status |
| `backend/nodes/enricher.py` | 最耗时阶段（批量爬取 + Tavily 兜底） |
| `backend/prompt_templates/seller_profile.py` | 委托方配置（单点修改） |
| `backend/services/scrape_engine.py` | 爬虫核心（DomainCircuitBreaker） |

## 规则

1. **异步优先**：所有 I/O 操作使用 `async/await`，httpx 用 `AsyncClient`
2. **日志规范**：使用 `logging.getLogger(__name__)`，不用 print
3. **Prompt 引用**：所有乐歌公司信息从 `seller_profile.py` 导入，prompt 中用 f-string 插入
4. **f-string 转义**：prompt 中的 `{company}` 等模板变量必须写成 `{{company}}`
5. **熔断器**：`DomainCircuitBreaker` 按路径分组（跳过 locale 段），threshold=2
6. **Tavily extract 超时**：15s（`asyncio.wait_for`），超时记录 warning 不 raise
7. **enricher 不重试 403/401**：收到这些状态码直接跳过 enhanced-static 策略
8. **briefing prompt 只做信息提取**：不做推理/推广建议（那是 Editor 的工作）
9. **Editor 负责推广分析**：综合 5 份简报 + seller_profile 生成合作机会分析

## 添加新研究节点的步骤

1. 在 `backend/nodes/researchers/` 创建新文件，继承 `BaseResearcher`
2. 在 `backend/prompt_templates/queries.py` 添加对应查询 prompt
3. 在 `backend/prompt_templates/briefings.py` 添加对应 briefing prompt
4. 在 `backend/graph.py` 注册节点并加入并行 fan-out
5. 在 `backend/classes/state.py` 的 `ResearchState` 添加对应数据字段
