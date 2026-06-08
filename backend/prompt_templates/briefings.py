"""
Briefing prompts for the research analyst nodes.
Each prompt generates a structured sub-report (分报告) from scraped documents.
"""

# ============================================================
# ANTI-HALLUCINATION RULE (injected into every briefing prompt)
# ============================================================
_NO_HALLUCINATION = """
⚠️ 准确性要求：
- 基于下方文档内容输出，每条信息尽量附 [来源](url) 引用。
- 不要捏造文档中不存在的事实（如虚构的发布会、合作协议、未来计划）。
- 不要把行业通用数据（市场规模等）说成是 {company} 的数据。
- 不要把其他公司的信息张冠李戴到 {company} 头上。
- 严禁捏造具体数字（金额、百分比、年份、增长率），除非文档中有原文。
- 文档有什么就写什么，有多少写多少，尽量全面丰富地提取有价值信息。
"""

COMPANY_BRIEFING_PROMPT = """Create a focused, yet comprehensive company briefing for {company}, a {industry} company based in {hq_location}.
Key requirements:
1. Start with: "{company} is a [what] that [does what] for [whom]"
2. Output the entire briefing in Chinese (简体中文). All content must be written in Chinese.
3. Structure using these headers and bullet points:

### 核心产品/服务
* List distinct products/features with pricing info
* Include product positioning and target pain points solved
* Highlight flagship/hero products most suitable for promotion

### 企业性质与自产能力
* Clarify if the company is a manufacturer, distributor, reseller, or hybrid
* List which products they manufacture/produce in-house (own factory, own brand production)
* List which products they source/resell from other brands
* Note any OEM/ODM capabilities or factory information
* Identify if they have their own production facilities and where

### 目标市场与用户痛点
* List specific target audiences and their key pain points
* List verified use cases and customer scenarios
* Identify unmet needs or underserved segments

### 产品差异化优势
* List unique selling propositions (USPs) vs competitors
* List proven advantages that resonate with buyers
* Highlight features that solve specific pain points

### 销售渠道与购买链接
* List all sales channels (official website, e-commerce platforms, partner stores)
* Include direct purchase links/URLs for each channel
* List authorized resellers and distributors
* Note which channels offer best deals or promotions

### 采购渠道与中国采购记录
* Identify known procurement/sourcing channels and supplier relationships ONLY if explicitly mentioned in documents
* Note any evidence of importing from China (Chinese suppliers, Made in China products, trade records) ONLY if documents contain explicit evidence
* List import/export data if available (customs records, trade databases)
* Identify which product categories they source internationally
* ⚠️ CRITICAL: This section requires HARD EVIDENCE from documents (e.g. customs records, supplier pages, import databases, trade show attendance). Do NOT fabricate procurement data. If no sourcing evidence exists in the documents, write: "* 在现有资料中未找到明确的采购渠道或中国采购记录"

4. Each bullet must be a single, complete fact
5. No paragraphs, only bullet points
6. Provide only the briefing. No explanations or commentary.
7. IMPORTANT: After each fact/sentence, add an inline citation linking to the source URL in the format [来源](url). Use the Source URL provided with each document. Example: * 该公司成立于2020年 [来源](https://example.com/about)
""" + _NO_HALLUCINATION


NEWS_BRIEFING_PROMPT = """Create a focused, yet comprehensive news briefing for {company}, a {industry} company based in {hq_location}.
Key requirements:
1. Output the entire briefing in Chinese (简体中文). All content must be written in Chinese.
2. Structure into these categories using bullet points:

### 新品发布与促销活动
* Recent product/service launches worth promoting
* Active promotional campaigns or limited-time offers
* New features or upgrades that address user pain points

### 合作与渠道拓展
* List new distribution partnerships with partner names and launch dates
* List platform integrations and marketplace expansions (Amazon, eBay, Alibaba, etc.)
* List co-marketing opportunities or joint promotional activities
* Note any reseller programs, affiliate partnerships, or channel partner announcements
* Identify strategic alliances or technology partnerships that create collaboration opportunities

### 市场反馈与口碑
* Customer reviews and satisfaction signals
* Awards, recognitions, or media coverage
* Social media buzz and trending topics about the brand

### 推广时机建议
* Identify newsworthy events that create promotion windows
* Note upcoming launches or events to leverage
* Suggest content angles based on recent news

3. Sort newest to oldest
4. One event per bullet point
5. If a section has no supporting evidence in the documents, write "* 在现有资料中未找到相关信息" for that section.
6. Provide only the briefing. Do not provide explanations or commentary.
7. IMPORTANT: After each fact/sentence, add an inline citation linking to the source URL in the format [来源](url). Use the Source URL provided with each document. Example: * 公司宣布新合作 [来源](https://example.com/news)
8. 时效性要求：只收录有明确日期（发布日期、新闻日期）的动态信息。如果文档中没有提供日期，或来源只是产品页面/公司官网的静态页面（没有新闻发布时间），则不要将其归入"近期动态"。产品页面本身不等于"新品发布"——除非文档中明确提到了上线/发布日期。
""" + _NO_HALLUCINATION


SOCIAL_MEDIA_BRIEFING_PROMPT = """Create a focused, yet comprehensive social media briefing for {company} (website: {company_url}), a {industry} company based in {hq_location}.
IMPORTANT: Only include information that is specifically about {company} ({company_url}). Ignore documents about unrelated people, other companies, or accounts that merely share a similar name.
Key requirements:
1. Output the entire briefing in Chinese (简体中文). All content must be written in Chinese.
2. Structure using these headers and bullet points:

### 社媒账号与粉丝基数
* List official social media accounts found (LinkedIn, Twitter/X, Instagram, Facebook, TikTok, WeChat, Douyin)
* Include follower counts or engagement metrics if available
* Note account verification status and posting frequency

### 最近社媒动态 (过去3个月)
* List recent posts, announcements, or content updates
* Highlight key messages or promotional campaigns
* Note customer engagement and response rates
* Identify trending topics or hashtags used by the company

### 用户评论与品牌声誉
* Summarize customer sentiment from social comments
* Note common praise points or complaints
* Highlight positive testimonials or user-generated content
* Identify potential pain points mentioned by customers

### 合作与影响者营销
* List any influencer partnerships or sponsored content collaborations
* Identify brand ambassadors, content creators, or thought leaders representing the brand
* Note collaborative content with other brands, creators, or industry partners
* Highlight co-branded campaigns or joint social media initiatives
* Identify potential partnership opportunities based on brand partnerships already mentioned

### 社媒营销策略洞察
* Identify content themes and posting patterns
* Note engagement tactics or promotional strategies
* Suggest content angles for partnership opportunities

3. One fact per bullet point
4. If a section has no supporting evidence in the documents, write "* 在现有资料中未找到相关信息" for that section.
5. Provide only the briefing. Do not provide explanations or commentary.
6. IMPORTANT: After each fact/sentence, add an inline citation linking to the source URL in the format [来源](url). Use the Source URL provided with each document. Example: * LinkedIn粉丝数10万+ [来源](https://example.com/linkedin)
""" + _NO_HALLUCINATION


BRIEFING_ANALYSIS_INSTRUCTION = """Analyze the following documents and extract key information. Provide only the briefing, no explanations or commentary:"""
