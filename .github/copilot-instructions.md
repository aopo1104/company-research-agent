# Copilot 项目规则

## 项目背景

这是一个多智能体公司研究平台，由乐歌股份（LoctekMotion）定制，用于 B2B 销售目标公司调研。系统自动化完成目标公司信息采集、整理、评估和报告生成。

**核心业务流程**：用户输入目标公司 URL → 系统自动研究该公司 → 生成中文研究报告（含合作机会分析）→ 可选生成开发信/PDF。

## 技术栈

| 层 | 技术 |
|---|---|
| 工作流引擎 | LangGraph (StateGraph, fan-out parallel) |
| LLM | Azure OpenAI GPT-4o |
| 搜索 API | Tavily API (search + extract) |
| 后端框架 | FastAPI + Uvicorn (port 9999) |
| 爬虫 | httpx + BeautifulSoup4 (多策略 + 域名熔断) |
| 前端 | React 18 + Vite + TypeScript + Tailwind CSS (port 3004) |
| 数据库 | MongoDB (可选) + MySQL (可选，aiomysql 异步连接池) |
| PDF 生成 | ReportLab |
| Python | 3.10+ |

## 核心目录

```
application.py                    # FastAPI 入口，所有 API 端点
backend/
  graph.py                        # LangGraph 工作流编排
  classes/state.py                # ResearchState 定义 + job_status
  nodes/                          # 管道各阶段节点
  prompt_templates/               # 所有 LLM prompt
    seller_profile.py             # ⚠️ 委托方公司配置（改这里切换客户）
  services/scrape_engine.py       # 爬虫 + DomainCircuitBreaker
  utils/url_filters.py            # URL 过滤规则
ui/src/                           # React 前端
```

## 开发规则

### 必须遵守

1. **所有 prompt 中的乐歌公司信息必须来自 `seller_profile.py`**，禁止在 prompt 文件中硬编码公司名、产品线。
2. **报告生成禁止编造**：每条事实必须有 `[来源](url)` 引用，来自简报原文。
3. **f-string 中的模板占位符必须双重转义**：`{{company}}`、`{{industry}}`、`{{hq_location}}`。
4. **修改 prompt 后不需要重启后端**，Python 模块在每次请求时动态导入。
5. **编辑 `scrape_engine.py` 时注意 DomainCircuitBreaker 的路径粒度**：跳过 locale 段（nl/be/en/fr），用首个有意义路径分组。
6. **SSE 事件流格式必须保持兼容**：前端依赖 `research_init` / `progress` / `scrape_source` / `complete` 事件类型。
7. **涉及工作流框架改动**（新增/删除节点、修改数据流、调整阶段顺序等）时，必须同步更新 `RESEARCH_PIPELINE.md`。
8. **代码改动完成后，默认执行并提示重启相关服务**：后端改动重启 `python application.py`，前端改动重启 `npm run dev`（修改 prompt 文件除外，见规则4）。
9. **任何代码改动导致与项目文档不一致时，必须同步更新相关文档**（包括本文件、`RESEARCH_PIPELINE.md`、`docs/` 下文档等）。

### 禁止事项

- 禁止在 briefing prompt 中加入推测性内容引导（推广分析仅在 Editor 阶段由 LLM 综合生成）
- 禁止直接修改 `backend/prompts.py`（它只是 re-export，改 `prompt_templates/` 下的源文件）
- 禁止在 enricher 中对 403 响应做重试（已有逻辑跳过）
- 禁止修改 `ResearchState` TypedDict 字段名（前后端依赖一致）

### 代码风格

- Python: 类型注解、async/await、logging（不用 print）
- 前端: 函数式组件、TypeScript 严格模式、Tailwind utility class
- 注释语言: 代码注释用中文，docstring 用英文
- Prompt 内容: 中文输出要求，英文指令

### 数据库变更

- **每次生成 SQL（建表、插入数据、变更结构等）必须新建一个独立文件**，存放在 `db/migrations/` 目录下。
- **文件命名格式**：`YYYYMMDD_HHmmss_<描述>.sql`，例如 `20260609_163942_product_catalog.sql`。
- `db/mysql_schema.sql` 仅作为完整 schema 参考，新增变更不要只改这个文件，必须同时在 `db/migrations/` 下留存独立迁移文件。

## 运行方式

```bash
# 后端
cd company-research-agent-main && python application.py

# 前端
cd ui && npm run dev
```

## 环境变量

```
AZURE_OPENAI_API_KEY / AZURE_OPENAI_API_INSTANCE_NAME / AZURE_OPENAI_API_DEPLOYMENT_NAME
TAVILY_API_KEY
MONGODB_URI (可选)
MYSQL_PASSWORD (可选，配置后启用 MySQL 持久化)
MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_DATABASE (均有默认值)
VITE_API_URL (前端，默认 /companyResearchAPI)
```

## 技术文档

详细工作流见 `RESEARCH_PIPELINE.md`（各阶段节点、数据流、状态字段、SSE 事件、API 端点的完整说明）。被问及流程细节时优先读取该文件。

> **注意**：本文件及所有项目文档描述的是当前系统的实现方式，不代表唯一方案。如有更优策略，可在征得用户同意后修改实现，并同步更新对应文档。
