"""
Search query generation prompts for all researcher nodes.
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

Your task: Generate 5 targeted search queries to research {{company}} ({{industry}}, {{hq_location}}).

Focus areas for queries:
1. Core products/services offered by the company
2. Target customers and market segments
3. Enterprise nature: is the company a manufacturer, retailer, reseller, or brand?
4. Sales channels (website, Amazon, physical stores, distributors)
5. Recent product launches or business updates
6. Procurement/sourcing from China (中国采购记录, Chinese suppliers, import records)

Examples of good queries:
- "{{company}} manufacturer or reseller own factory production"
- "{{company}} product sourcing China suppliers import"
- "{{company}} OEM ODM manufacturing capability"
- "{{company}} China procurement import records trade data"
- "{{company}} products pricing official website"
- "site:{{company}} product categories"
- "site:{{company}} solutions catalog collections"

""" + QUERY_FORMAT_GUIDELINES


NEWS_SCANNER_QUERY_PROMPT = f"""You are a B2B sales research expert for {SELLER_NAME_EN}.
Your task: Generate 5 targeted search queries to find the latest news and events about {{company}} ({{industry}}, {{hq_location}}).

Focus areas for queries:
1. Recent product launches or updates (last 12 months)
2. Promotional campaigns or sales events
3. Customer reviews and brand reputation

""" + QUERY_FORMAT_GUIDELINES


SOCIAL_MEDIA_ANALYZER_QUERY_PROMPT = f"""You are a B2B sales research expert for {SELLER_NAME_EN}.
Your task: Generate 5 targeted search queries to find social media content and digital presence for {{company}} ({{industry}}, {{hq_location}}).
Company website: {{company_url}}

IMPORTANT: Use the company's domain name (e.g. "bol.com") or full company name in your queries to avoid matching unrelated accounts with similar short names. For example, search for "bol.com" instead of just "Bol" to find the actual company's social media presence.

Focus areas for queries:
1. Social media official accounts (LinkedIn, Twitter/X， Instagram, Facebook)
2. Recent social media posts or updates (last 3 months)
3. Customer engagement and comments on social platforms
4. Social media follower count, engagement rate, content strategy
5. User reviews on social platforms or review sites and Community discussions or forum mentions

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

