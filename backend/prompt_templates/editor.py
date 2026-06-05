"""
Editor and report compilation prompts.
Used by the Editor node to compile sub-briefings into a final report.
"""

from .seller_profile import SELLER_CONTEXT_ZH, SELLER_PRODUCTS_ZH

EDITOR_SYSTEM_MESSAGE = "You are an expert B2B sales research analyst. You compile comprehensive reports from provided briefings. You ONLY report facts that appear in the provided briefings. You NEVER invent, assume, or extrapolate information. Every factual claim must have a [来源](url) citation copied directly from the briefings."

COMPILE_CONTENT_PROMPT = """你收到了关于 {company} 的5份研究简报（公司、行业、财务、新闻、社媒）。

你的任务：将它们整合为一份全面、详细的中文 Markdown 研究报告。

🎯 核心目标 — 最大化信息提取：
- 简报中每一条有 [来源](url) 引用的信息都应该出现在最终报告中
- 不要遗漏任何有价值的数据点（数字、日期、金额、百分比、人名、产品名等）
- 内容宁多勿少：如果简报中提到了，就写进报告
- 同一事实出现在多个简报中时，合并去重，保留最详细的版本

🚨 严禁编造规则：
1. 你只能使用下方简报中明确存在的信息。绝对禁止添加简报中没有的事实。
2. 每条事实性陈述必须带有 [来源](url) 引用，直接从简报中复制。
3. 如果某节在简报中没有对应内容，写"暂无相关信息"。
4. 保留所有 [来源](url) 的原始URL格式，一字不改。
5. 不要把其他公司的信息写进 {company} 的描述中。

📝 写作要求：
- 使用连贯的段落叙述，不要只是罗列要点
- 在段落叙述中自然嵌入 [来源](url) 引用
- 相关信息可以组织成逻辑通顺的段落，但内容必须来自简报
- 数据密集的内容（如融资轮次、竞品列表）可以用列表形式

📋 输出结构：

## 公司概况
包含：公司简介、成立时间、总部地点、创始人/管理层、员工规模、公司愿景等基本信息。
[主要从 company briefing 提取]

## 核心产品与服务
包含：主要产品线、技术特点、服务模式、核心竞争力、专利/技术壁垒等。
[主要从 company briefing 提取]

## 商业模式与目标市场
包含：收入模式、定价策略、目标客户群体、应用场景、用户痛点、客户案例等。
[从 company briefing 和 industry briefing 提取]

## 市场竞争格局
包含：市场规模、增长率、主要竞争对手、市场份额、行业趋势、技术发展方向等。
[主要从 industry briefing 提取]

## 财务与融资情况
包含：融资历史（轮次、金额、投资方）、估值、收入规模、盈利状况、财务指标等。
[主要从 financial briefing 提取]

## 采购渠道与供应链
包含：供应商关系、中国采购记录、制造合作伙伴、供应链布局等。
[从 company briefing 和 financial briefing 提取]

## 近期动态
包含：最新新闻、产品发布、合作公告、市场扩张、管理层变动、奖项等。
注意：只收录有明确日期的动态信息。如果简报中的信息没有附带日期、或来源只是产品页面（没有发布时间），则不属于"近期动态"，不要写入此节。
[主要从 news briefing 提取]

## 最近社媒动态
包含：社媒账号信息、近期发布内容、用户评论与品牌声誉、影响者合作、社媒营销策略等。
[主要从 social_media briefing 提取]

## 推广与合作机会分析
""" + SELLER_CONTEXT_ZH + """

**本节任务**：综合以上所有简报信息，从乐歌的角度出发，分析两个层面：
A) 乐歌如何通过 {company} 推广/销售自有产品（推广机会）
B) 乐歌与 {company} 可以建立哪些合作关系（合作切入点）

每条分析必须基于简报中的具体事实，并标注 [来源](url)。

### 产品匹配度评估
- {company} 的用户群体是否有对乐歌产品的真实需求？结合简报中的用户画像和痛点分析 [来源](url)
- {company} 目前销售/采购哪些与乐歌产品重叠的品类？哪个品类切入最自然？[来源](url)
- {company} 是否有中国采购记录或现有中国供应商？（有 = 乐歌可直接对接的供货路径）[来源](url)

### 推广机会
- {company} 是否提供 Retail Media / Branded Shelf / 展示广告等付费推广服务？乐歌能以多少成本触达其用户？[来源](url)
- 当前有哪些推广时机（季节性、节日、新品发布期）可以利用？[来源](url)

### 合作切入点
根据 {company} 的企业性质（从简报中判断）选择合适的合作模式：
- 若为零售商/电商平台 → 乐歌作为第三方卖家入驻，优先品类？入驻门槛/要求？[来源](url)
- 若为品牌商/制造商 → OEM/ODM 合作，乐歌提供升降机芯或白牌产品？[来源](url)
- 若为分销商/代理商 → 区域独家代理乐歌产品线的可能性？[来源](url)
- 是否有明确的禁售品类限制乐歌入场？[来源](url)

### 风险与障碍
- {company} 是否已有固定的同类竞品供应商？[来源](url)
- 市场准入、产品认证（CE/RoHS等）、物流等方面的潜在障碍 [来源](url)

### 乐歌行动建议（总结）
基于以上分析，给出 2-3 条具体可执行的建议：
「建议X：[合作/推广方式] — [依据：简报事实 [来源](url)] — [第一步行动]」

IMPORTANT: 每条分析必须有简报事实支撑 [来源](url)。无信息的维度写"暂无相关信息"。

以下是5份简报原文：

{content}
"""


CONTENT_SWEEP_SYSTEM_MESSAGE = "You are a report editor. Your job is to polish the report structure and remove only clearly fabricated content. You preserve ALL cited content. You NEVER add new information or new citations."

CONTENT_SWEEP_PROMPT = """优化以下关于 {company} 的研究报告的结构和可读性。

📌 必须保留的内容：
1. 所有带有 [来源](url) 引用的句子和段落 — 一字不改地保留。
2. 所有章节标题（## 开头）。
3. "暂无相关信息"占位文字。
4. 连接上下文的过渡性语句（即使没有独立引用，只要前后文有引用支撑）。

🔧 可以做的优化：
1. 修复 Markdown 格式问题（标题层级、列表格式等）。
2. 合并完全重复的信息（保留信息更完整的版本）。
3. 删除明显的无来源推测性内容（如"预计未来将..."、"有望成为..."等无引用的猜测）。
4. 确保段落之间逻辑通顺。

🚫 禁止操作：
1. 不要删除任何带 [来源](url) 的内容。
2. 不要添加新信息、新数据或新引用。
3. 不要修改 URL 链接。
4. 不要把已有内容改写得面目全非。

输出优化后的完整报告：

{content}
"""
