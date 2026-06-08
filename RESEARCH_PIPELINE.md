# 公司研究智能体 - 完整工作流详解 (v2.4 - 2026年6月)

本文档基于实际代码精确整理，每个细节均对应具体文件和实现。

---

## 项目结构

```
application.py              # FastAPI 入口 (端口 9999)
backend/
  graph.py                  # LangGraph 工作流编排
  prompts.py                # Prompt 统一导出
  classes/state.py          # InputState / ResearchState / job_status
  nodes/
    grounding.py            # 阶段1 - 官网抓取
    researchers/            # 阶段2 - 5个并行研究节点
      company.py / industry.py / financial.py / news.py / social_media.py
    collector.py            # 阶段3 - 数据汇总
    curator.py              # 阶段4 - 质量筛选
    enricher.py             # 阶段5 - 内容充实
    briefing.py             # 阶段6 - 简报生成
    editor.py               # 阶段7 - 报告编译
    company_info_extractor.py  # 前置 - URL信息提取
  prompt_templates/
    COMPANY.md              # 委托方公司信息 (乐歌)
    seller_profile.py       # 委托方变量定义
    briefings.py            # 简报 Prompt
    editor.py               # 编辑 Prompt
    queries.py              # 查询生成 Prompt
    quick_research.py       # 快速研究 Prompt
    email_outreach.py       # 开发信 Prompt
  services/
    scrape_engine.py        # 多策略爬虫 (httpx/JSON-LD/Tavily)
    pdf_service.py          # ReportLab PDF 生成
    mongodb.py              # MongoDB 持久化 (可选)
  utils/
    references.py           # 引用处理
    url_filters.py          # URL 过滤规则
ui/                         # React + Vite + TypeScript 前端
```

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
      │  【阶段2】3个研究节点并行 (LangGraph fan-out)    │
      │                                                  │
      │  ① CompanyAnalyzer  (company.py)                │
      │     GPT-4o 生成4条查询                           │
      │     Tavily 搜索 (search_depth=advanced)          │
      │     每条查询取5条结果 → 共20条文档               │
      │                                                  │
      │  ② NewsScanner  (news.py)                       │
      │     GPT-4o 生成4条查询                           │
      │     Tavily 搜索 (topic=news)                     │
      │     每条查询取5条结果 → 共20条文档               │
      │                                                  │
      │  ③ SocialMediaAnalyzer  (social_media.py)       │
      │     GPT-4o 生成查询                              │
      │     Tavily 搜索 (include_domains 限定社媒域名)   │
      │     每条查询取8条结果，优先社媒平台              │
      │     目标域名: LinkedIn/Twitter/X/Facebook        │
      │             /YouTube/TikTok/Glassdoor等          │
      │                                                  │
      │  3个节点同时运行，LangGraph自动调度              │
      │  总计: ~60条搜索结果文档                         │
      └────────────┬─────────────────────────────────────┘
           │ company_data / news_data / social_media_data
                   ▼
      ┌────────────────────────────────┐
      │  【阶段3】Collector            │  collector.py
      │  数据汇总统计（纯逻辑，无API）  │
      │  检查3类数据是否存在            │
      │  计数每类文档数量               │
      │  生成统计日志推送给前端         │
      └────────────┬───────────────────┘
                   │ 统计信息 + 原始数据不变
                   ▼
      ┌────────────────────────────────┐
      │  【阶段4】Curator              │  curator.py
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
      │  5. 公司相关性检查              │
      │     company/news需验证公司相关  │
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
      │  效果: ~60文档 → ~40文档       │
      │  (通过率约67%)                 │
      └────────────┬───────────────────┘
           │ curated_company_data / curated_news_data /
           │ curated_social_media_data / reference_titles /
                   │ reference_info
                   ▼
      ┌────────────────────────────────┐
      │  【阶段5】Enricher             │  enricher.py
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
      │  - Semaphore 限制5个批并发     │
      │  - 域名熔断器 (连续失败2次     │
      │    即跳过同域名剩余URL)        │
      │  - 单URL超时: 自研12s/Tavily15s│
      │  - 典型成功率:                 │
      │    87% 自研爬虫               │
      │    11% Tavily Extract         │
      │     2% 失败(保留原摘要)       │
      └────────────┬───────────────────┘
                   │ 每个文档新增 raw_content 字段
                   ▼
      ┌────────────────────────────────┐
      │  【阶段6】Briefing             │  briefing.py
      │  生成3份中文简报               │
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
      │  3份简报:                      │
      │  1. COMPANY_BRIEFING_PROMPT   │
      │     公司基本信息/产品/团队     │
      │     /商业模式/竞争优势         │
      │                                │
      │  2. NEWS_BRIEFING_PROMPT      │
      │     最近新闻/公告/合作/奖项    │
      │     (必须有日期证明"最近")    │
      │                                │
      │  3. SOCIAL_MEDIA_BRIEFING     │
      │     品牌声誉/用户评价          │
      │     /社媒互动/行业评论         │
      │                                │
      │  防幻觉规则:                   │
      │  - 严格基于文档，不捏造数据    │
      │  - 采购渠道无据则注明未找到    │
      │  - 所有声明附引用链接          │
      └────────────┬───────────────────┘
                   │ company_briefing / news_briefing /
                   │ social_media_briefing
                   ▼
      ┌────────────────────────────────┐
      │  【阶段7】Editor               │  editor.py
      │  2阶段编译最终报告             │
      │  模型: Azure GPT-4o (流式输出) │
      │                                │
      │  阶段7-1: COMPILE              │
      │  COMPILE_CONTENT_PROMPT       │
      │  - 整合3份简报为连贯叙述       │
      │  - 非简单拼接，去除重复内容    │
      │  - 流式逐段返回给前端          │
      │                                │
      │  阶段7-2: SWEEP                │
      │  CONTENT_SWEEP_PROMPT         │
      │  - 格式化优化Markdown结构      │
      │  - 移除元评论/AI说明文字       │
      │  - 验证引用链接完整            │
      │  - 流式逐段返回给前端          │
      │                                │
      │  Grounding Gate (后处理):      │
      │  - 逐行验证报告是否有简报支撑  │
      │  - Token overlap ≥ 35%        │
      │  - 含引用链接的行自动保留      │
      │  - 短文本 (<10字) 视为过渡保留 │
      │  - 防止 LLM 幻觉进入最终报告   │
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

## Company Overview
  核心产品与服务 / Leadership / 商业模式 / 竞争优势

## Industry Overview
  市场规模 / 竞争格局 / 发展趋势 / 主要挑战

## Financial Overview
  融资历史 / Revenue Model / 财务健康度

## News
  * 新闻项1 (附日期)
  * 新闻项2 (附日期)

## Social Media & Reputation
  品牌声誉 / 用户真实反馈 / 行业评价

## References
  - [标题1](url1)
  - [标题2](url2)
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

# 阶段2 输出
company_data: list[dict]   # 每条: {url, title, content, score, query}
industry_data: list[dict]
financial_data: list[dict]
news_data: list[dict]
social_media_data: list[dict]

# 阶段4 输出
curated_company_data: list[dict]
curated_news_data: list[dict]
curated_social_media_data: list[dict]
reference_titles: list[str]   # 所有URL的标题
reference_info: dict           # URL → 完整元信息

# 阶段5 输出
# 以上各curated_*_data的每条文档新增 raw_content 字段

# 阶段6 输出
company_briefing: str
news_briefing: str
social_media_briefing: str

# 阶段7 输出
report: str                # 最终Markdown报告（流式构建）
messages: list             # LangChain消息历史
```

---

## 性能参考

| 阶段 | 耗时 | 备注 |
|------|------|------|
| CompanyInfoExtractor | 3-8秒 | 用户操作时异步执行 |
| 【阶段1】Grounding | 5-15秒 | 取决于网站响应速度 |
| 【阶段2】3并行搜索 | 12-20秒 | 3节点同时运行 |
| 【阶段3】Collector | <1秒 | 纯统计，无IO |
| 【阶段4】Curator | 2-5秒 | 纯逻辑筛选 |
| 【阶段5】Enricher | 30-60秒 | 最慢阶段，批量爬取+熔断 |
| 【阶段6】Briefing | 12-25秒 | 3份简报并行生成 |
| 【阶段7】Editor | 15-25秒 | 2轮LLM流式 + Grounding Gate |
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
| `scrape_source` | 爬取来源通知 | Enricher 每个URL完成 |
| `llm_status` | LLM 调用状态 | Enricher 爬取时 (非LLM) |
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
| v2.3 | 2026-06 | 新增快速研究/翻译端点、委托方配置 |
| v2.4 | 2026-06 | 项目清理; Enricher域名熔断器; Editor Grounding Gate; 阶段编号精简为7级 |

---

**更新时间**: 2026年6月8日
