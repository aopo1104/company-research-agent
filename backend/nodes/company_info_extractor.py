"""
================================================================================
company_info_extractor.py - 从官网提取公司基本信息
================================================================================
从公司官网爬取内容，用 Azure GPT-4o 提取：公司名、行业、总部地址

输入: company_url
输出: {company_name, industry, hq_location}
"""

import json
import logging
import os
import re
from typing import Optional
from urllib.parse import urlparse

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tavily import AsyncTavilyClient

logger = logging.getLogger(__name__)

# TLD → country mapping for common country-code TLDs
TLD_COUNTRY_MAP = {
    "nl": "Netherlands", "de": "Germany", "fr": "France", "uk": "United Kingdom",
    "co.uk": "United Kingdom", "jp": "Japan", "cn": "China", "kr": "South Korea",
    "it": "Italy", "es": "Spain", "br": "Brazil", "au": "Australia",
    "ca": "Canada", "in": "India", "ru": "Russia", "se": "Sweden",
    "no": "Norway", "dk": "Denmark", "fi": "Finland", "pl": "Poland",
    "be": "Belgium", "at": "Austria", "ch": "Switzerland", "pt": "Portugal",
    "mx": "Mexico", "ar": "Argentina", "za": "South Africa", "sg": "Singapore",
    "hk": "Hong Kong", "tw": "Taiwan", "th": "Thailand", "my": "Malaysia",
    "id": "Indonesia", "vn": "Vietnam", "ph": "Philippines", "nz": "New Zealand",
    "ie": "Ireland", "cz": "Czech Republic", "hu": "Hungary", "ro": "Romania",
    "gr": "Greece", "tr": "Turkey", "il": "Israel", "ae": "UAE",
    "sa": "Saudi Arabia", "cl": "Chile", "co": "Colombia",
}

# URL path language/country codes
PATH_COUNTRY_MAP = {
    "nl": "Netherlands", "de": "Germany", "fr": "France", "en-gb": "United Kingdom",
    "jp": "Japan", "ja": "Japan", "cn": "China", "zh": "China",
    "kr": "South Korea", "ko": "South Korea", "it": "Italy", "es": "Spain",
    "br": "Brazil", "pt-br": "Brazil", "au": "Australia", "en-au": "Australia",
}

EXTRACTION_SYSTEM = """You are an expert at extracting company information from website content.
Your task is to analyze the website content and extract:
1. 所属行业 (Industry)
2. 总部所在国家 (Country)
3. 总部地址 (Headquarters Location - city, country)

Return ONLY valid JSON in this exact format:
{{
    "industry": "extracted industry or empty string",
    "country": "country name or empty string",
    "hq_location": "city, country or just country if city unknown"
}}

Rules:
- Use best-effort inference from public knowledge, domain TLD, URL path locale, and name clues
- If a country hint is provided, use it to determine the company's operating country
- If still unknown after best effort, use empty string ""
- Industry should be concise (e.g., "E-commerce", "Consulting", "Manufacturing")
- Location should be city, country format when possible; country alone is acceptable
- Return ONLY the JSON, no additional text"""

EXTRACTION_PROMPT = """Infer company information from these known inputs:

Company name: {company_name}
Website URL: {company_url}
Domain: {domain}
Country hint from URL: {country_hint}

You may use broad public/business knowledge up to your knowledge cutoff and domain naming signals.
The country hint is derived from the URL's TLD or path locale — use it as strong evidence for the company's country.
Return concise values. If truly unknown, return empty string.
Return the JSON object only."""


class CompanyInfoExtractor:
    """从官网提取公司信息的工具类"""

    def __init__(self):
        """初始化提取器，配置 Azure GPT-4o"""
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_instance = os.getenv("AZURE_OPENAI_API_INSTANCE_NAME")
        azure_deployment = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")
        azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

        if not azure_api_key or not azure_instance or not azure_deployment:
            raise ValueError("Missing Azure OpenAI configuration")

        azure_endpoint = azure_instance.strip()
        if azure_endpoint.startswith("http://") or azure_endpoint.startswith("https://"):
            pass
        elif "." in azure_endpoint:
            azure_endpoint = f"https://{azure_endpoint}"
        else:
            azure_endpoint = f"https://{azure_endpoint}.openai.azure.com"

        self.llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0,
            max_retries=0,
        )
        tavily_key = os.getenv("TAVILY_API_KEY")
        self.tavily_client = AsyncTavilyClient(api_key=tavily_key) if tavily_key else None

    async def _crawl_with_tavily(self, company_url: str) -> dict:
        if not self.tavily_client:
            return {}

        try:
            extraction = await self.tavily_client.crawl(
                url=company_url,
                max_depth=1,
                max_breadth=10,
                extract_depth="advanced",
                instructions=(
                    "Find pages that describe the company profile, products/services, "
                    "about/team/company info and contact/location details."
                ),
            )

            site_scrape = {}
            for item in extraction.get("results", []) or []:
                raw = (item or {}).get("raw_content", "")
                if not raw:
                    continue
                page_url = (item or {}).get("url", company_url)
                site_scrape[page_url] = {
                    "raw_content": raw,
                    "title": (item or {}).get("title", ""),
                    "source": "company_website",
                    "method": "tavily",
                }

            return site_scrape
        except Exception as e:
            logger.warning(f"Tavily crawl fallback failed for {company_url}: {e}")
            return {}

    async def _search_with_tavily(self, company_url: str, company_name: str) -> str:
        if not self.tavily_client:
            return ""

        parsed = urlparse(company_url if "://" in company_url else f"https://{company_url}")
        host = parsed.hostname or company_url
        queries = [
            f"{company_name} company headquarters",
            f"{company_name} industry",
            f"site:{host} about company",
        ]

        snippets = []
        for query in queries:
            try:
                result = await self.tavily_client.search(
                    query,
                    search_depth="advanced",
                    max_results=5,
                    include_raw_content=False,
                )
                for item in result.get("results", []) or []:
                    title = (item or {}).get("title", "")
                    content = (item or {}).get("content", "")
                    if title or content:
                        snippets.append(f"Title: {title}\nContent: {content}")
            except Exception as e:
                logger.warning(f"Tavily search fallback failed for query '{query}': {e}")

        return "\n\n".join(snippets)[:12000]

    async def extract_from_url(self, company_url: str) -> dict:
        """
        从URL提取公司信息
        
        Args:
            company_url: 公司官网URL
            
        Returns:
            {
                "company_name": str,
                "industry": str,
                "hq_location": str,
                "success": bool,
                "message": str
            }
        """
        try:
            logger.info(f"Starting company info extraction from {company_url}")

            # 公司名固定走规则提取，不调用 LLM
            company_name = self._domain_to_company_name(company_url)
            parsed = urlparse(company_url if "://" in company_url else f"https://{company_url}")
            domain = (parsed.hostname or "").lower()

            # 从 URL 推断国家线索
            country_hint = self._infer_country_from_url(company_url)

            # 用 LLM 基于 URL/公司名直接推断行业和总部（无爬虫）
            logger.info(f"Calling Azure GPT-4o to infer industry and HQ from URL/domain (country_hint={country_hint})...")
            extraction_prompt = ChatPromptTemplate.from_messages([
                ("system", EXTRACTION_SYSTEM),
                ("user", EXTRACTION_PROMPT),
            ])

            chain = extraction_prompt | self.llm | StrOutputParser()

            result_text = await chain.ainvoke({
                "company_name": company_name,
                "company_url": company_url,
                "domain": domain,
                "country_hint": country_hint or "unknown",
            })
            logger.info(f"LLM extraction result: {result_text}")

            # 第四步：解析 JSON 结果
            import json

            result_text = result_text.strip()
            # 尝试找到 JSON 对象
            if "{" in result_text and "}" in result_text:
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1
                json_str = result_text[json_start:json_end]
                data = json.loads(json_str)
            else:
                data = json.loads(result_text)

            hq_location = data.get("hq_location", "").strip()
            country = data.get("country", "").strip()
            # If hq_location is empty but country was inferred, use country as location
            if not hq_location and country:
                hq_location = country

            return {
                "success": True,
                "message": "信息提取成功",
                "company_name": company_name,
                "industry": data.get("industry", "").strip(),
                "hq_location": hq_location,
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {
                "success": False,
                "message": f"信息提取失败（JSON解析错误）",
                "company_name": self._domain_to_company_name(company_url),
                "industry": "",
                "hq_location": "",
            }
        except Exception as e:
            logger.error(f"Error extracting company info from {company_url}: {e}")
            return {
                "success": False,
                "message": f"信息提取失败：{str(e)}",
                "company_name": self._domain_to_company_name(company_url),
                "industry": "",
                "hq_location": "",
            }

    def _infer_country_from_url(self, company_url: str) -> str:
        """从 URL 的 TLD 和路径中推断国家"""
        parsed = urlparse(company_url if "://" in company_url else f"https://{company_url}")
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower().strip("/")

        # 1) Check ccTLD (e.g. .nl, .de, .co.uk)
        parts = host.split(".")
        if len(parts) >= 3 and f"{parts[-2]}.{parts[-1]}" in TLD_COUNTRY_MAP:
            return TLD_COUNTRY_MAP[f"{parts[-2]}.{parts[-1]}"]
        if len(parts) >= 2 and parts[-1] in TLD_COUNTRY_MAP:
            return TLD_COUNTRY_MAP[parts[-1]]

        # 2) Check URL path for locale codes (e.g. /nl/nl/, /de/, /fr/)
        path_segments = [s for s in path.split("/") if s]
        for seg in path_segments[:2]:
            seg_lower = seg.lower()
            if seg_lower in PATH_COUNTRY_MAP:
                return PATH_COUNTRY_MAP[seg_lower]

        return ""

    def _domain_to_company_name(self, company_url: str) -> str:
        parsed = urlparse(company_url if "://" in company_url else f"https://{company_url}")
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        label = host.split(".")[0] if host else ""
        label = re.sub(r"[-_]+", " ", label).strip()
        return label.title() if label else "Unknown"

    def _clean_title_candidate(self, title: str) -> str:
        if not title:
            return ""

        candidate = title.strip()
        for sep in ["|", " - ", " — ", " • ", ":"]:
            if sep in candidate:
                candidate = candidate.split(sep)[0].strip()
                break

        # Remove common boilerplate words on home pages
        candidate = re.sub(r"\b(home|homepage|official site|welcome)\b", "", candidate, flags=re.I).strip()
        candidate = re.sub(r"\s{2,}", " ", candidate)
        return candidate

    def _extract_company_name_from_site(self, company_url: str, site_scrape: dict) -> str:
        # Deprecated for current no-crawl flow; keep as fallback utility.
        titles = []
        if company_url in site_scrape and site_scrape[company_url].get("title"):
            titles.append(site_scrape[company_url].get("title", ""))

        for page in site_scrape.values():
            title = (page or {}).get("title", "")
            if title:
                titles.append(title)

        for title in titles:
            cleaned = self._clean_title_candidate(title)
            if 2 <= len(cleaned) <= 80:
                return cleaned

        return self._domain_to_company_name(company_url)
