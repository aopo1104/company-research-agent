"""
Editor and report compilation prompts.
Used by the Editor node to compile sub-briefings into a final report.
"""

EDITOR_SYSTEM_MESSAGE = "You are an expert B2B sales analyst that produces accurate, well-structured research reports in Chinese."

COMPILE_CONTENT_PROMPT = """You have been provided with a company briefing, industry analysis, financial data, and news briefing for {company}.

Your task is to compile these into a SINGLE, COHESIVE Markdown report in Chinese (简体中文) WITHOUT losing any details.

⚠️ 严格规定 — 禁止幻觉输出：
- 只能使用下方各分报告中已有的信息，禁止添加或捏造新事实。
- 保留原有的 [来源](url) 引用。
- 尽量完整保留所有分报告中的有价值内容，不要过度删减。

🚫 严禁张冠李戴：
- 不要把其他公司的信息写进 {company} 的公司描述中。
- 行业通用市场数据放在"市场竞争格局"节中即可。

⚠️ IMPORTANT FORMATTING RULES:
1. Preserve ALL bullet points and citations from the source briefings
2. Do not summarize or shorten — keep ALL details
3. Do not add introduction or conclusion paragraphs
4. Do not add information that was not in the briefings
5. Every citation [来源](url) from the original briefings MUST be preserved

Use this structure:

# {company} 企业研究报告

## 公司概况
[From company briefing - 核心产品/服务 and company overview]

## 核心产品与服务
[From company briefing - 核心产品/服务]

## 企业性质与自产能力
[From company briefing - 企业性质与自产能力]

## 目标市场与用户痛点
[From company briefing - 目标市场与用户痛点]

## 采购渠道与中国采购记录
[From company briefing - 采购渠道与中国采购记录, and financial briefing - 供应链与采购渠道]

## 市场竞争格局
[From industry briefing - 竞争格局]

## 近期动态
[From news briefing - all sections]

## 财务与融资情况
[From financial briefing - 融资与投资 and 营收模式与定价]

## 推广机会与建议
[From company briefing - 推广机会分析, news briefing - 推广时机建议, industry briefing - 推广趋势与渠道洞察]
"""


CONTENT_SWEEP_SYSTEM_MESSAGE = "You are an expert editor that reviews research reports for accuracy and completeness."

CONTENT_SWEEP_PROMPT = """Review and clean the following research report about {company}.

⚠️ 准确性要求：
- 保留所有有来源支撑的有价值内容。
- 禁止添加原文中不存在的新信息。
- 删除明显捏造的内容（如无来源的虚构合作/发布会/未来计划）。
- 删除张冠李戴的内容（把其他公司的信息说成 {company} 的）。
- 保留所有关于 {company} 的合理内容和分析。

Cleanup tasks:
1. Remove any duplicate information
2. Fix broken markdown formatting
3. Ensure all section headers are properly formatted
4. Remove any meta-commentary like "no information found" or "data unavailable"
5. DELETE any bullet point that is clearly about a different company (not {company}) and mistakenly attributed to {company}
6. Preserve ALL factual content and citations — do not over-delete
7. Keep bullets even if they lack a citation, as long as the content is factually reasonable

Output the cleaned report ONLY. No commentary.

Report to clean:
{content}
"""
