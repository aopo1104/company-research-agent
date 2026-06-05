# 公司研究智能体 - 完整工作流详解 (v2.3 - 2026年6月)

本文档基于实际代码精确整理，每个细节均对应具体文件和实现。

---

## 整体流程图

```
用户输入: 公司URL (必填) + 公司名 / 行业 / 总部位置 (可选)
                   │
                   ▼ [如果只填了URL，自动提取公司信息]
      ┌────────────────────────────────┐
      │  CompanyInfoExtractor          │  前置 API 端点
      │  (company_info_extractor.py)   │  POST /extract-company-info
      │  Azure GPT-4o → 提取公司名     │  → 自动填充表单
      │  / 行业 / 总部位置             │
      └────────────┬───────────────────┘
                   │ company / industry / hq_location
                   ▼
      ┌────────────────────────────────┐
      │  POST /research                │  application.py
      │  生成 job_id (UUID)            │
      │  asyncio.create_task 启动后台  │
      │  立即返回 job_id 给前端        │
      │  前端连接 SSE: /research/      │
      │    {job_id}/stream             │
      └────────────┬───────────────────┘
                   │
                   ▼
      ┌────────────────────────────────┐
      │  【阶段1】Grounding            │  grounding.py
      │  官网抓取                      │
      │  策略1: httpx + BeautifulSoup  │  最多50个页面
      │  策略2: JSON-LD 结构化数据     │  内容净化
      │  策略3: 反爬Header模拟浏览器   │  max 20000字符
      │  失败兜底: Tavily Crawl API    │  成功率 ~90%
      └────────────┬───────────────────┘
                   │ site_scrape {url: {raw_content, title, method}}
                   ▼
      ┌──────────────────────────────────────────────────┐
      │  【阶段2-3】5个研究节点并行 (LangGraph fan-out)  │
      │                                                  │
      │  ① CompanyAnalyzer  (company.py)                │
      │     GPT-4o 生成4条查询                           │
      │     Tavily 搜索 (search_depth=advanced)          │
      │     每条查询取5条结果 → 共20条文档               │
      │                                                  │
      │  ② IndustryAnalyzer  (industry.py)              │
      │     GPT-4o 生成4条查询                           │
      │     Tavily 搜索 (search_depth=advanced)          │
      │     每条查询取5条结果 → 共20条文档               │
      │                                                  │
      │  ③ FinancialAnalyst  (financial.py)              │
      │     GPT-4o 生成4条查询                           │
      │     Tavily 搜索 (topic=finance)                  │
      │     每条查询取5条结果 → 共20条文档               │
      │                                                  │
      │  ④ NewsScanner  (news.py)                       │
      │     GPT-4o 生成4条查询                           │
      │     Tavily 搜索 (topic=news)                     │
      │     每条查询取5条结果 → 共20条文档               │
      │                                                  │
      │  ⑤ SocialMediaAnalyzer  (social_media.py)       │
      │     GPT-4o 生成查询                              │
      │     Tavily 搜索 (include_domains 限定社媒域名)   │
      │     每条查询取8条结果，优先社媒平台              │
      │     目标域名: LinkedIn/Twitter/X/Facebook        │
      │             /YouTube/TikTok/Glassdoor等          │
      │                                                  │
      │  5个节点同时运行，LangGraph自动调度              │
      │  总计: ~90-100条搜索结果文档                    │
      └────────────┬─────────────────────────────────────┘
                   │ company_data / industry_data /
                   │ financial_data / news_data / social_media_data
                   ▼
      ┌────────────────────────────────┐
      │  【阶段4】Collector            │  collector.py
      │  数据汇总统计（纯逻辑，无API）  │
      │  检查4类数据是否存在            │  注: 统计financial/news/
      │  计数每类文档数量               │  industry/company 4类
      │  生成统计日志推送给前端         │
      └────────────┬───────────────────┘
                   │ 统计信息 + 原始数据不变
                   ▼
      ┌────────────────────────────────┐
      │  【阶段5】Curator              │  curator.py
      │  内容质量筛选                  │
      │                                │
      │  筛选规则（按顺序）:            │
      │  1. URL规范化去重              │
      │     移除query/fragment参数     │
      │  2. 低价值URL过滤              │
      │     登录页/搜索结果/社媒等     │
      │  3. 评分筛选                   │
      │     Tavily score ≥ 0.4        │
      │     或 官网来源(无论分数)      │
      │  4. 垃圾内容检测               │
      │     过滤Dictionary定义页等     │
      │  5. 行业相关性检查 (industry)  │
      │     验证内容是否与公司/行业相关 │
      │  6. Top 30限制                 │
      │     每类别最多30条             │
      │  7. 引用收集                   │
      │     保存titles和reference_info │
      │                                │
      │  特殊处理:                     │
      │  社媒部分 (_RELAXED_SECTIONS)  │
      │  - 宽松筛选，不强制去重        │
      │  - 防止品牌声誉内容丢失        │
      │                                │
      │  效果: ~90文档 → ~55文档      │
      │  (通过率约75%)                 │
      └────────────┬───────────────────┘
                   │ curated_company_data / curated_industry_data /
                   │ curated_financial_data / curated_news_data /
                   │ curated_social_media_data / reference_titles /
                   │ reference_info
                   ▼
      ┌────────────────────────────────┐
      │  【阶段6】Enricher             │  enricher.py
      │  补全每个文档的完整内容         │
      │                                │
      │  处理策略:                     │
      │  1. 自研爬虫优先               │
      │     httpx + BeautifulSoup      │
      │     降低API成本                │
      │  2. Tavily Extract API兜底      │
      │     自研爬虫失败时调用         │
      │                                │
      │  并发策略:                     │
      │  - 每批 20个URL               │
      │  - 并发 3个批次               │
      │  - 典型成功率:                 │
      │    87% 自研爬虫               │
      │    11% Tavily Extract         │
      │     2% 失败(保留原摘要)       │
      └────────────┬───────────────────┘
                   │ 每个文档新增 raw_content 字段
                   ▼
      ┌────────────────────────────────┐
      │  【阶段7】Briefing             │  briefing.py
      │  生成5份中文简报               │
      │  模型: Azure GPT-4o            │
      │  temperature=0 (确定性输出)    │
      │                                │
      │  文档处理:                     │
      │  - 官网页面优先排序            │
      │    (source=company_website)    │
      │  - 按Tavily分数降序排列        │
      │  - 单文档最大8000字符          │
      │  - 总输入最大120000字符        │
      │                                │
      │  5份简报:                      │
      │  1. COMPANY_BRIEFING_PROMPT   │
      │     公司基本信息/产品/团队     │
      │     /商业模式/竞争优势         │
      │                                │
      │  2. INDUSTRY_BRIEFING_PROMPT  │
      │     市场规模/竞争格局          │
      │     /趋势/挑战                 │
      │                                │
      │  3. FINANCIAL_BRIEFING_PROMPT │
      │     融资/财务指标/估值         │
      │     /采购渠道(需硬证据)        │
      │                                │
      │  4. NEWS_BRIEFING_PROMPT      │
      │     最近新闻/公告/合作/奖项    │
      │     (必须有日期证明"最近")    │
      │                                │
      │  5. SOCIAL_MEDIA_BRIEFING     │
      │     品牌声誉/用户评价          │
      │     /社媒互动/行业评论         │
      │                                │
      │  防幻觉规则:                   │
      │  - 严格基于文档，不捏造数据    │
      │  - 采购渠道无据则注明未找到    │
      │  - 所有声明附引用链接          │
      └────────────┬───────────────────┘
                   │ company_briefing / industry_briefing /
                   │ financial_briefing / news_briefing /
                   │ social_media_briefing
                   ▼
      ┌────────────────────────────────┐
      │  【阶段8】Editor               │  editor.py
      │  2阶段编译最终报告             │
      │  模型: Azure GPT-4o (流式输出) │
      │                                │
      │  阶段8-1: COMPILE              │
      │  COMPILE_CONTENT_PROMPT       │
      │  - 整合5份简报为连贯叙述       │
      │  - 非简单拼接，去除重复内容    │
      │  - 社媒部分宽松处理            │
      │    (_RELAXED_SECTIONS保留全部) │
      │  - 流式逐段返回给前端          │
      │                                │
      │  阶段8-2: SWEEP                │
      │  CONTENT_SWEEP_PROMPT         │
      │  - 格式化优化Markdown结构      │
      │  - 移除元评论/AI说明文字       │
      │  - 验证引用链接完整            │
      │  - 流式逐段返回给前端          │
      │                                │
      │  引用处理:                     │
      │  - 提取正文中所有URL           │
      │  - 与reference_titles对比      │
      │  - 生成规范的参考资料节        │
      └────────────┬───────────────────┘
                   │ 流式Markdown报告 (SSE)
                   ▼
      ┌────────────────────────────────┐
      │  最终输出                       │
      │  ✅ Markdown格式研究报告        │
      │  ✅ 5大部分 + 参考资料          │
      │  ✅ 可下载PDF                   │
      └────────────────────────────────┘
```

---

## 最终报告结构

```markdown
# {公司名} Research Report

## 目录

## 【公司简报】
  公司概览 / 核心产品与服务 / 商业模式 / 竞争优势 / 团队

## 【行业简报】
  行业现状 / 市场规模 / 竞争格局 / 发展趋势 / 主要挑战

## 【财务简报】
  收入规模 / 融资历史 / 盈利能力 / 财务健康度 / 采购渠道

## 【新闻简报】
  最新动态 (每条必须有日期) / 重要公告 / 合作信息 / 里程碑

## 【最近社媒动态】
  品牌声誉 / 用户真实反馈 / 社媒互动 / 行业评价

## 参考资料
  - [标题1](url1)
  - [标题2](url2)
  ...
```

---

## 技术栈

| 层次 | 技术 | 用途 |
|------|------|------|
| 工作流引擎 | LangGraph StateGraph | 节点编排、并行调度 |
| LLM | Azure OpenAI GPT-4o | 查询生成、简报、报告、开发信、翻译 |
| 搜索 | Tavily API | 网络搜索、内容提取 |
| 爬虫 | httpx + BeautifulSoup4 | 官网抓取、内容充实 |
| API框架 | FastAPI + Uvicorn | HTTP服务、SSE流式 |
| 前端 | React 18 + Vite + TypeScript | UI界面 |
| 进程管理 | PM2 | 前后端统一管理 |
| 数据库(可选) | MongoDB (pymongo) | 任务持久化存储 |
| PDF生成 | ReportLab | Markdown → PDF |

---

## 委托方配置

本系统为 **LoctekMotion（乐歌股份）** 定制：

- 公司信息权威来源：`backend/prompt_templates/COMPANY.md`
- 代码变量定义：`backend/prompt_templates/seller_profile.py`
- 所有 Prompt 文件通过导入 `seller_profile.py` 获取公司上下文
- 切换委托方时只需修改 `seller_profile.py` 和 `COMPANY.md`

---

## 数据流（State字段）

```python
# InputState / ResearchState 关键字段

# 用户输入
company: str               # 公司名
company_url: str           # 官网URL
hq_location: str           # 总部位置
industry: str              # 行业
job_id: str                # 任务ID (UUID)

# 阶段1 输出
site_scrape: dict          # {url: {raw_content, title, method, source}}

# 阶段2-3 输出
company_data: list[dict]   # 每条: {url, title, content, score, query}
industry_data: list[dict]
financial_data: list[dict]
news_data: list[dict]
social_media_data: list[dict]

# 阶段5 输出
curated_company_data: list[dict]
curated_industry_data: list[dict]
curated_financial_data: list[dict]
curated_news_data: list[dict]
curated_social_media_data: list[dict]
reference_titles: list[str]   # 所有URL的标题
reference_info: dict           # URL → 完整元信息

# 阶段6 输出
# 以上各curated_*_data的每条文档新增 raw_content 字段

# 阶段7 输出
company_briefing: str
industry_briefing: str
financial_briefing: str
news_briefing: str
social_media_briefing: str

# 阶段8 输出
report: str                # 最终Markdown报告（流式构建）
messages: list             # LangChain消息历史
```

---

## 性能参考

| 阶段 | 耗时 | 备注 |
|------|------|------|
| CompanyInfoExtractor | 3-8秒 | 用户操作时异步执行 |
| 【阶段1】Grounding | 5-15秒 | 取决于网站响应速度 |
| 【阶段2-3】5并行搜索 | 15-25秒 | 5节点同时运行 |
| 【阶段4】Collector | <1秒 | 纯统计，无IO |
| 【阶段5】Curator | 2-5秒 | 纯逻辑筛选 |
| 【阶段6】Enricher | 30-60秒 | 最慢阶段，批量爬取 |
| 【阶段7】Briefing | 20-40秒 | 5份简报串行生成 |
| 【阶段8】Editor | 15-25秒 | 2轮LLM流式输出 |
| **总计** | **90-180秒** | **平均约2分钟** |

---

## API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 健康检查 (返回 `{"message": "Alive"}`) |
| `/research` | POST | 启动完整研究任务，返回 job_id |
| `/research/{job_id}/stream` | GET | SSE 流式读取进度和最终结果 |
| `/research/{job_id}/report` | GET | 轮询获取报告（兼容非SSE场景）|
| `/research/{job_id}` | GET | 获取任务详情（需 MongoDB）|
| `/research/pdf/{filename}` | GET | 下载已生成的 PDF 文件 |
| `/research-quick` | POST | 快速研究：单轮 Tavily 搜索 + 单次 LLM 生成报告 |
| `/extract-company-info` | POST | 从 URL 提取公司名/行业/位置 |
| `/generate-email` | POST | 基于报告生成 B2B 开发信（JSON 格式）|
| `/generate-pdf` | POST | 从 Markdown 内容生成 PDF 流式下载 |
| `/translate` | POST | 将报告翻译为指定语言（默认中文）|

---

## 快速研究模式 (`/research-quick`)

```
POST /research-quick
Body: { company, company_url?, industry?, hq_location? }
```

轻量级研究路径，不走 LangGraph 管线：

1. 构造 3-4 条搜索查询（公司概况 + 新闻 + 采购 + 官网site:）
2. Tavily 并行搜索，每条取 5 结果，共 ~15 条
3. 单次 Azure GPT-4o 调用，使用 `QUICK_RESEARCH_SYSTEM_PROMPT`
4. 直接返回 Markdown 报告（无流式、无 job_id）

适用场景：快速了解公司概况，无需深度研究时使用。

---

## SSE 事件类型

前端通过 EventSource 订阅 `/research/{job_id}/stream`:

| type 字段 | 含义 | 触发时机 |
|-----------|------|----------|
| `progress` | 当前执行节点名 | 每个 LangGraph 节点完成时 |
| `research_init` | 研究启动确认 | 任务创建时 |
| `complete` | 最终报告(Markdown) | 研究全部完成 |
| `error` | 错误信息 + 失败阶段 | 任何异常 |
| `: keepalive` | SSE 注释心跳 | 每 ~15秒无数据时 |

> 各节点内部可向 `job_status[job_id]["events"]` 队列追加自定义事件，
> SSE 循环会 FIFO 弹出并推送给前端。

---

## 版本历史

| 版本 | 时间 | 变更 |
|------|------|------|
| v1.0 | 2025-12 | 初始版本，4个研究节点 |
| v2.0 | 2026-05 | 新增SocialMediaAnalyzer第5节点 |
| v2.1 | 2026-06 | 社媒宽松筛选、活动日志移除 |
| v2.2 | 2026-06 | 文档按代码精确重写 |
| v2.3 | 2026-06 | 新增快速研究/翻译端点、委托方配置、COMPANY.md整理 |

---

**更新时间**: 2026年6月5日
