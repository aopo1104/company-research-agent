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
from typing import Optional

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..services.scrape_engine import crawl_site

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM = """You are an expert at extracting company information from website content.
Your task is to analyze the website content and extract:
1. 公司名称 (Company Name)
2. 所属行业 (Industry)
3. 总部地址 (Headquarters Location)

Return ONLY valid JSON in this exact format:
{{
  "company_name": "extracted name or empty string",
  "industry": "extracted industry or empty string",
  "hq_location": "extracted location or empty string"
}}

Rules:
- If information is not found, use empty string ""
- Company name should be the official/legal name
- Industry should be concise (e.g., "Software", "Consulting", "Manufacturing")
- Location should be city, country format when possible
- Return ONLY the JSON, no additional text"""

EXTRACTION_PROMPT = """Please extract company information from this website content:

{content}

Return the JSON object with extracted information."""


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

        self.llm = AzureChatOpenAI(
            azure_endpoint=f"https://{azure_instance}.openai.azure.com",
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0,
            max_retries=0,
        )

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

            # 第一步：爬取网页内容
            logger.info("Crawling website content...")
            site_scrape = await crawl_site(company_url, max_pages=10, max_depth=0)

            if not site_scrape:
                logger.warning(f"No content extracted from {company_url}")
                return {
                    "success": False,
                    "message": f"无法从 {company_url} 爬取内容",
                    "company_name": "",
                    "industry": "",
                    "hq_location": "",
                }

            # 第二步：合并爬取的内容
            combined_content = "\n\n".join(
                [data.get("raw_content", "")[:2000] for data in site_scrape.values()]
            )

            if not combined_content.strip():
                logger.warning(f"No valid content extracted from {company_url}")
                return {
                    "success": False,
                    "message": f"网页内容为空",
                    "company_name": "",
                    "industry": "",
                    "hq_location": "",
                }

            logger.info(f"Extracted {len(combined_content)} characters from website")

            # 第三步：用 LLM 提取信息
            logger.info("Calling Azure GPT-4o to extract company info...")
            extraction_prompt = ChatPromptTemplate.from_messages([
                ("system", EXTRACTION_SYSTEM),
                ("user", EXTRACTION_PROMPT),
            ])

            chain = extraction_prompt | self.llm | StrOutputParser()

            result_text = await chain.ainvoke({"content": combined_content})
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

            return {
                "success": True,
                "message": "信息提取成功",
                "company_name": data.get("company_name", "").strip(),
                "industry": data.get("industry", "").strip(),
                "hq_location": data.get("hq_location", "").strip(),
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {
                "success": False,
                "message": f"信息提取失败（JSON解析错误）",
                "company_name": "",
                "industry": "",
                "hq_location": "",
            }
        except Exception as e:
            logger.error(f"Error extracting company info from {company_url}: {e}")
            return {
                "success": False,
                "message": f"信息提取失败：{str(e)}",
                "company_name": "",
                "industry": "",
                "hq_location": "",
            }
