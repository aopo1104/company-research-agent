"""
================================================================================
base.py - 研究节点基类 (Stage 2-3)
================================================================================
定义查询生成和文档搜索的通用逻辑

继承关系:
  BaseResearcher (本文件)
    ├── CompanyAnalyzer (company.py) - 公司信息
    ├── IndustryAnalyzer (industry.py) - 行业分析
    ├── FinancialAnalyst (financial.py) - 财务分析
    └── NewsScanner (news.py) - 新闻扫描

流程:
  1. generate_queries(): 使用Azure GPT-4o生成4条搜索查询
  2. search_documents(): 并行执行Tavily搜索
  3. run(): 汇总查询和文档到state

各分析器使用不同的:
  - analyst_type: 用于标识分析器类型
  - prompt: 特定领域的查询生成提示
  - topic: Tavily搜索的专题 (可选: news, finance)
  
搜索结果数据结构:
  {
    "url": "https://...",
    "title": "...",
    "content": "...",  # 摘要 (不是完整内容)
    "score": 0.92,     # Tavily相关性评分
    "query": "..."     # 来源查询
  }

典型运行:
  4个节点并行执行
  ├─ CompanyAnalyzer: 生成4个查询 → 执行搜索 → 收集20个文档
  ├─ IndustryAnalyzer: 生成4个查询 → 执行搜索 → 收集20个文档
  ├─ FinancialAnalyst: 生成4个查询 (topic=finance) → 收集20个文档
  └─ NewsScanner: 生成4个查询 (topic=news) → 收集20个文档
  
  总计: 16个查询 × 5结果 = 80个文档
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from tavily import AsyncTavilyClient

from ...classes import ResearchState
from ...classes.state import job_status
from ...utils.references import clean_title
from ...prompts import QUERY_FORMAT_GUIDELINES, RESEARCHER_SYSTEM_MESSAGE

logger = logging.getLogger(__name__)

class BaseResearcher:
    def __init__(self):
        """初始化研究节点
        
        配置:
          - Tavily AsyncClient: 异步搜索API
          - Azure GPT-4o: LangChain集成，用于查询生成
        """
        tavily_key = os.getenv("TAVILY_API_KEY")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_instance = os.getenv("AZURE_OPENAI_API_INSTANCE_NAME")
        azure_deployment = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")
        azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        
        if not tavily_key or not azure_api_key or not azure_instance or not azure_deployment:
            raise ValueError("Missing API keys")
            
        self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
        self.llm = AzureChatOpenAI(
            azure_endpoint=f"https://{azure_instance}.openai.azure.com",
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0,
            streaming=True,
        )
        self.analyst_type = "base_researcher"

    @property
    def analyst_type(self) -> str:
        """分析器类型标识 (由子类覆写设置)"""
        if not hasattr(self, '_analyst_type'):
            raise ValueError("Analyst type not set by subclass")
        return self._analyst_type

    @analyst_type.setter
    def analyst_type(self, value: str):
        """设置分析器类型标识
        
        子类应设置为:
          - "company_analyzer"
          - "industry_analyzer"
          - "financial_analyst"
          - "news_scanner"
        """
        self._analyst_type = value

    def _parse_queries_from_json(self, text: str) -> List[str]:
        """Parse JSON-formatted LLM output to extract query strings.
        
        Handles outputs like:
          ```json
          {"queries": [{"query": "...", "category": "..."}, ...]}
          ```
        Returns list of query strings, or empty list if parsing fails.
        """
        # Strip markdown code fences
        cleaned = re.sub(r'```(?:json)?\s*', '', text).strip()
        cleaned = cleaned.rstrip('`').strip()
        
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and 'queries' in data:
                return [item['query'] for item in data['queries'] if isinstance(item, dict) and 'query' in item]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        
        # Fallback: try to find JSON object anywhere in text
        json_match = re.search(r'\{[^{}]*"queries"\s*:\s*\[.*?\]\s*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if 'queries' in data:
                    return [item['query'] for item in data['queries'] if isinstance(item, dict) and 'query' in item]
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        
        # Last resort: extract "query" values with regex
        query_matches = re.findall(r'"query"\s*:\s*"([^"]+)"', text)
        if query_matches:
            return query_matches
        
        return []

    async def generate_queries(self, state: Dict, prompt: str):
        """Generate search queries and yield events as they're created"""
        company = state.get("company", "Unknown Company")
        industry = state.get("industry", "Unknown Industry")
        hq_location = state.get("hq_location", "Unknown")
        current_year = datetime.now().year
        job_id = state.get("job_id")
        
        logger.info(f"=== GENERATE_QUERIES START: job_id={job_id}, analyst={self.analyst_type} ===")
        if not job_id:
            logger.warning(f"⚠️ NO JOB_ID in state! Keys: {list(state.keys())}")
        
        try:
            logger.info(f"Generating queries for {company} as {self.analyst_type}, job_id={job_id}")
            
            # Create prompt template using LangChain
            query_prompt = ChatPromptTemplate.from_messages([
                ("system", RESEARCHER_SYSTEM_MESSAGE),
                ("user", """Researching {company} in {year}, as of {date}.
{task_prompt}
{format_guidelines}""")
            ])
            
            # Create LCEL chain
            chain = query_prompt | self.llm
            
            queries = []
            current_query = ""
            current_query_number = 1

            # Stream queries using LangChain's astream
            if job_id and job_id in job_status:
                job_status[job_id]["events"].append({
                    "type": "llm_call",
                    "purpose": f"{self.analyst_type} 查询生成",
                    "message": f"🤖 LLM调用: 生成 {self.analyst_type} 搜索查询"
                })
            async for chunk in chain.astream({
                "company": company,
                "industry": industry,
                "hq_location": hq_location,
                "year": current_year,
                "date": datetime.now().strftime("%B %d, %Y"),
                "task_prompt": prompt,
                "format_guidelines": QUERY_FORMAT_GUIDELINES.format(company=company)
            }):
                current_query += chunk.content
                
                # Yield query generation progress
                event = {
                    "type": "query_generating",
                    "query": current_query,
                    "query_number": current_query_number,
                    "category": self.analyst_type
                }
                
                # Update job status if job_id provided
                if job_id:
                    try:
                        logger.info(f"job_id={job_id}, job_id in job_status={job_id in job_status}")
                        if job_id in job_status:
                            job_status[job_id]["events"].append(event)

                        else:
                            logger.warning(f"job_id {job_id} not found in job_status. Available keys: {list(job_status.keys())[:3]}")
                    except Exception as e:
                        logger.error(f"Error appending event: {e}")
                
                yield event
                
                # Parse completed queries on newline
                if '\n' in current_query:
                    parts = current_query.split('\n')
                    current_query = parts[-1]
                    
                    for query in parts[:-1]:
                        query = query.strip()
                        if query:
                            queries.append(query)
                            event = {
                                "type": "query_generated",
                                "query": query,
                                "query_number": len(queries),
                                "category": self.analyst_type
                            }
                            
                            # Update job status if job_id provided
                            if job_id:
                                try:
                                    if job_id in job_status:
                                        job_status[job_id]["events"].append(event)
                                    else:
                                        logger.warning(f"job_id {job_id} not found in job_status for query_generated")
                                except Exception as e:
                                    logger.error(f"Error appending query_generated event: {e}")
                            
                            yield event
                            current_query_number += 1

            # Add remaining query
            if current_query.strip():
                queries.append(current_query.strip())
                yield {
                    "type": "query_generated",
                    "query": current_query.strip(),
                    "query_number": len(queries),
                    "category": self.analyst_type
                }
            
            # Parse JSON output to extract actual query strings
            # The LLM outputs JSON like: {"queries": [{"query": "...", "category": "..."}]}
            full_text = "\n".join(queries)
            parsed_queries = self._parse_queries_from_json(full_text)
            
            if parsed_queries:
                queries = parsed_queries
            else:
                # Fallback: filter out obvious non-query lines
                queries = [q for q in queries if len(q) > 5 and not q.startswith(('```', '{', '}', '"queries"', ']'))]
            
            if not queries:
                raise ValueError(f"No queries generated for {company}")

            queries = queries[:8]  # Limit to 8 queries
            logger.info(f"Final queries for {self.analyst_type}: {queries}")
            
            yield {"type": "queries_complete", "queries": queries, "count": len(queries)}
            
        except Exception as e:
            logger.error(f"Error generating queries for {company}: {e}")
            raise RuntimeError(f"Fatal API error - query generation failed: {str(e)}") from e

    def _get_search_params(self) -> Dict[str, Any]:
        """Get search parameters based on analyst type"""
        params = {
            "search_depth": "basic",
            "include_raw_content": False,
            "max_results": 5
        }
        
        topic_map = {
            "news_analyzer": "news",
            "financial_analyzer": "finance"
        }
        
        if topic := topic_map.get(self.analyst_type):
            params["topic"] = topic
            
        return params
    
    def _process_search_result(self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Process a single search result into standardized format"""
        if not result.get("content") or not result.get("url"):
            return {}
            
        url = result.get("url")
        title = clean_title(result.get("title", "")) if result.get("title") else ""
        
        # Reset empty or invalid titles
        if not title or title.lower() == url.lower():
            title = ""
        
        return {
            "title": title,
            "content": result.get("content", ""),
            "query": query,
            "url": url,
            "source": "web_search",
            "score": result.get("score", 0.0)
        }

    async def search_documents(self, state: ResearchState, queries: List[str]):
        """Execute all Tavily searches in parallel and yield events"""
        if not queries:
            logger.error("No valid queries to search")
            yield {"type": "error", "error": "No valid queries to search"}
            return

        # Yield start event
        yield {
            "type": "search_started",
            "message": f"Searching {len(queries)} queries",
            "total_queries": len(queries)
        }

        # Execute all searches in parallel
        search_params = self._get_search_params()
        job_id = state.get('job_id')
        if job_id and job_id in job_status:
            job_status[job_id]["events"].append({
                "type": "tavily_search",
                "count": len(queries),
                "message": f"📡 Tavily搜索: {len(queries)} 条查询"
            })
        search_tasks = [self.tavily_client.search(query, **search_params) for query in queries]

        try:
            results = await asyncio.gather(*search_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error during parallel search execution: {e}")
            yield {"type": "error", "error": str(e)}
            return

        # Process and merge results
        merged_docs = {}
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.error(f"Search failed for query '{query}': {result}")
                yield {"type": "query_error", "query": query, "error": str(result)}
                continue
                
            for item in result.get("results", []):
                if doc := self._process_search_result(item, query):
                    merged_docs[doc["url"]] = doc

        # Yield completion event
        yield {
            "type": "search_complete",
            "message": f"Found {len(merged_docs)} documents",
            "total_documents": len(merged_docs),
            "queries_processed": len(queries),
            "merged_docs": merged_docs
        }
