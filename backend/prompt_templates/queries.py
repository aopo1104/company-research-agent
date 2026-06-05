"""
Search query generation prompts for all four researcher nodes.
These prompts generate targeted search queries for Tavily.
"""

from .seller_profile import SELLER_CONTEXT_EN, SELLER_NAME_EN, SELLER_PRODUCTS_SHORT_EN

# ============================================================
# RESEARCHER SYSTEM MESSAGE - shared by all four analyzers
# ============================================================
RESEARCHER_SYSTEM_MESSAGE = """You are researching {company}, a company in the {industry} industry, headquartered in {hq_location}.
Company website: {company_url}

""" + SELLER_CONTEXT_EN

QUERY_FORMAT_GUIDELINES = """
Format your response as a JSON object with the following structure:
{{
  "queries": [
    {{"query": "search query 1", "category": "category1"}},
    {{"query": "search query 2", "category": "category2"}},
    ...
  ]
}}
Only include the JSON object in your response, no other text.

Hard requirements for generated queries:
1) Include at least 2 website-targeted queries using site: operator (e.g. site:company.com product category solutions).
2) Include at least 3 queries explicitly containing product/category terms such as product, products, category, categories, solutions, catalog, collections.
"""

COMPANY_ANALYZER_QUERY_PROMPT = f"""You are a B2B sales research expert for {SELLER_NAME_EN}.
{SELLER_NAME_EN} sells: {SELLER_PRODUCTS_SHORT_EN}.

Your task: Generate 8 targeted search queries to research {{company}} ({{industry}}, {{hq_location}}).

Focus areas for queries:
1. Core products/services offered by the company
2. Target customers and market segments
3. Enterprise nature: is the company a manufacturer, retailer, reseller, or brand?
4. Self-manufacturing capability: does the company have its own factory or production line? (自产能力)
5. Sales channels (website, Amazon, physical stores, distributors)
6. Company background and founding story
7. Recent product launches or business updates
8. Procurement/sourcing from China (中国采购记录, Chinese suppliers, import records)

Examples of good queries:
- "{{company}} manufacturer or reseller own factory production"
- "{{company}} product sourcing China suppliers import"
- "{{company}} OEM ODM manufacturing capability"
- "{{company}} China procurement import records trade data"
- "{{company}} products pricing official website"
- "site:{{company}} product categories"
- "site:{{company}} solutions catalog collections"

""" + QUERY_FORMAT_GUIDELINES


FINANCIAL_ANALYZER_QUERY_PROMPT = f"""You are a B2B sales research expert for {SELLER_NAME_EN}.
Your task: Generate 8 targeted search queries to research the financial situation and supply chain of {{company}} ({{industry}}, {{hq_location}}).

Focus areas for queries:
1. Funding rounds and investors
2. Revenue, valuation, or financial metrics
3. Business model and pricing strategy
4. Supply chain and procurement channels
5. Sourcing from China or Chinese manufacturers (供应链中国采购)
6. Trade show attendance (e.g. Canton Fair, Global Sources, Alibaba)
7. Import/export records or customs data related to the company
8. Marketing/promotion budget or spend signals

Examples of good queries:
- "{{company}} funding rounds investors valuation"
- "{{company}} revenue annual report financial"
- "{{company}} China import customs records sourcing"
- "{{company}} supplier manufacturer China trade data"
- "{{company}} Canton Fair Global Sources Alibaba sourcing"
- "site:{{company}} procurement suppliers product lines"

""" + QUERY_FORMAT_GUIDELINES


INDUSTRY_ANALYZER_QUERY_PROMPT = f"""You are a B2B sales research expert for {SELLER_NAME_EN}.
Your task: Generate 8 targeted search queries to research the industry landscape for {{company}} ({{industry}}, {{hq_location}}).

Focus areas for queries:
1. Market size and growth trends in this industry
2. Key competitors and their products/strategies
3. Industry pain points and unmet customer needs
4. Emerging trends and technology shifts
5. Distribution and marketing channels used in this space
6. Regulatory or compliance factors
7. Buyer behavior and purchasing patterns
8. Opportunities for ergonomic/lifting product suppliers in this market
9. Product/category structures used by competitors in this industry

""" + QUERY_FORMAT_GUIDELINES


NEWS_SCANNER_QUERY_PROMPT = f"""You are a B2B sales research expert for {SELLER_NAME_EN}.
Your task: Generate 8 targeted search queries to find the latest news and events about {{company}} ({{industry}}, {{hq_location}}).

Focus areas for queries:
1. Recent product launches or updates (last 12 months)
2. New partnerships or distribution agreements
3. Promotional campaigns or sales events
4. Customer reviews and brand reputation
5. Awards, media coverage, or recognition
6. Expansion plans or new market entries
7. Leadership changes or company announcements
8. Social media buzz or trending content related to {{company}}

""" + QUERY_FORMAT_GUIDELINES


SOCIAL_MEDIA_ANALYZER_QUERY_PROMPT = f"""You are a B2B sales research expert for {SELLER_NAME_EN}.
Your task: Generate 8 targeted search queries to find social media content and digital presence for {{company}} ({{industry}}, {{hq_location}}).
Company website: {{company_url}}

IMPORTANT: Use the company's domain name (e.g. "bol.com") or full company name in your queries to avoid matching unrelated accounts with similar short names. For example, search for "bol.com" instead of just "Bol" to find the actual company's social media presence.

Focus areas for queries:
1. Social media official accounts (LinkedIn, Twitter/X, Instagram, Facebook, TikTok, WeChat, Douyin)
2. Recent social media posts or updates (last 3 months)
3. Customer engagement and comments on social platforms
4. Influencer mentions or partnerships
5. Social media follower count, engagement rate, content strategy
6. User reviews on social platforms or review sites
7. Community discussions or forum mentions
8. Viral content or trending topics related to {{company}}

Examples of good queries:
- "site:linkedin.com/company {{company}}"
- "{{company_url}} LinkedIn official page followers"
- "{{company_url}} Twitter X official account"
- "{{company_url}} Instagram Facebook social media presence"
- "{{company}} official TikTok account {{hq_location}}"
- "{{company_url}} social media marketing strategy"
- "{{company}} customer reviews social media {{industry}}"
- "{{company_url}} brand social media engagement"

""" + QUERY_FORMAT_GUIDELINES

