# 项目概览

## 一句话描述

基于 LangGraph 多智能体的公司研究平台，为乐歌股份 B2B 销售团队自动生成目标公司研究报告和合作机会分析。

## 核心价值

1. **自动化调研**：输入公司 URL，自动完成全网信息采集
2. **结构化报告**：包含公司概况、产品、竞争格局、财务、供应链、近期动态
3. **合作分析**：从乐歌 B2B 卖家视角评估合作可行性
4. **辅助工具**：自动生成 B2B 开发信、PDF 报告

## 用户角色

| 角色 | 使用方式 |
|------|----------|
| 乐歌销售人员 | 通过 Web UI 输入目标客户网址，获取研报 |
| 开发者 | 维护/扩展研究管道、优化 prompt |

## 运行环境

- **本地开发**：Windows，`python application.py` + `npm run dev`
- **部署**：Docker 或直接部署（参见 `Dockerfile` / `docker-compose.yml`）
- **LangGraph Cloud**：支持通过 `langgraph.json` 部署到 LangGraph Platform

## 依赖服务

| 服务 | 必须？ | 用途 |
|------|--------|------|
| Azure OpenAI | ✅ | GPT-4o 调用 |
| Tavily API | ✅ | 搜索 + 网页提取 |
| MongoDB | ❌ | 任务持久化（无则内存存储） |

## 相关文档

- [RESEARCH_PIPELINE.md](../RESEARCH_PIPELINE.md) — 完整管道技术细节
- [architecture.md](architecture.md) — 系统架构图
- [dev-workflow.md](dev-workflow.md) — 开发工作流
- [coding-standards.md](coding-standards.md) — 编码规范
