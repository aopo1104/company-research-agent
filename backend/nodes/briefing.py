"""
================================================================================
briefing.py - 简报生成阶段 (Stage 7)
================================================================================
使用Azure GPT-4o为4个类别生成中文简报

输入: curated_*_data (~50个完整文档)
输出: company_briefing, industry_briefing, financial_briefing, news_briefing

4个简报类别:
  1. Company: 公司基本信息、产品、团队、商业模式
  2. Industry: 市场规模、竞争、趋势、挑战
  3. Financial: 融资历史、财务指标、估值、采购渠道
  4. News: 最近新闻、公告、合作、奖项

防幻觉设计:
  - 所有简报包含_NO_HALLUCINATION规则：基于文档内容，附引用[来源](url)
  - 采购渠道需要硬证据，无法找到则说"未找到明确的采购渠道"
  - 严禁捏造数据、虚构事件、张冠李戴

文档处理:
  - 官网页面优先 (source='company_website') - 保证准确性
  - 按Tavily分数排序 - 高分优先
  - 单文档截断8000字符 - 避免过长
  - 总长度120000字符 - LLM上下文限制

典型简报: 1000-2000字/类别
"""

import asyncio
import logging
import os
import random
from typing import Any, Dict, List, Union

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..classes import ResearchState
from ..classes.state import job_status
from ..prompts import (
    COMPANY_BRIEFING_PROMPT,
    NEWS_BRIEFING_PROMPT,
    SOCIAL_MEDIA_BRIEFING_PROMPT,
    BRIEFING_ANALYSIS_INSTRUCTION
)

logger = logging.getLogger(__name__)

class Briefing:
    """简报生成器 - 为4个研究类别生成中文简报"""
    
    def __init__(self) -> None:
        """初始化Briefing，配置Azure GPT-4o
        
        max_doc_length: 单个文档最大内容长度 (8000字符)
        """
        self.max_doc_length = 8000  # 单文档最大长度
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_instance = os.getenv("AZURE_OPENAI_API_INSTANCE_NAME")
        azure_deployment = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")
        azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        
        if not azure_api_key or not azure_instance or not azure_deployment:
            raise ValueError("Missing Azure OpenAI configuration: AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_INSTANCE_NAME, or AZURE_OPENAI_API_DEPLOYMENT_NAME")

        azure_endpoint = azure_instance.strip()
        if azure_endpoint.startswith("http://") or azure_endpoint.startswith("https://"):
            pass
        elif "." in azure_endpoint:
            azure_endpoint = f"https://{azure_endpoint}"
        else:
            azure_endpoint = f"https://{azure_endpoint}.openai.azure.com"
        
        # 配置LangChain Azure OpenAI客户端
        self.llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_version=azure_version,
            api_key=azure_api_key,
            temperature=0,  # 确定性输出
            max_retries=0
        )

    def _get_category_prompt(self, category: str) -> str:
        """获取类别对应的Prompt模板
        
        Args:
            category: company/industry/financial/news
            
        Returns:
            对应的Prompt字符串
        """
        prompts = {
            'company': COMPANY_BRIEFING_PROMPT,
            'news': NEWS_BRIEFING_PROMPT,
            'social_media': SOCIAL_MEDIA_BRIEFING_PROMPT,
        }
        return prompts.get(category, 
                          "Create a focused, informative and insightful research briefing on the company: {company} in the {industry} industry based on the provided documents.")
    
    def _prepare_documents(self, docs: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """准备并格式化文档供简报生成
        
        文档排序优先级:
          1. 官网页面优先 (source='company_website') - 第一方信息最可信
          2. Tavily分数降序 (high score = high relevance)
          
        长度限制:
          - 单文档: 8000字符
          - 总长度: 120000字符
        
        Args:
            docs: 文档字典 或 文档列表
            
        Returns:
            格式化的文档文本 (Markdown格式)
        """
        # Convert dict to list if needed
        if isinstance(docs, dict):
            docs_list = list(docs.values())
        else:
            docs_list = docs if isinstance(docs, list) else []
        
        if not docs_list:
            return ""
        
        # Sort: company_website first, then by score descending
        docs_list.sort(key=lambda d: (-int(d.get('source') == 'company_website'), -float(d.get('score', 0))))
        
        doc_texts = []
        total_length = 0
        
        for doc in docs_list:
            source_url = doc.get('url', '')
            title = doc.get('title', '') or doc.get('url', '')
            content = doc.get('raw_content', '') or doc.get('content', '')
            
            if len(content) > self.max_doc_length:
                content = content[:self.max_doc_length] + "... [content truncated]"
            
            doc_entry = f"Source URL: {source_url}\nTitle: {title}\n\nContent: {content}"
            if total_length + len(doc_entry) < 120000:  # Keep under limit
                doc_texts.append(doc_entry)
                total_length += len(doc_entry)
            else:
                break
        
        separator = "\n" + "-" * 40 + "\n"
        return f"{separator}{separator.join(doc_texts)}{separator}"

    async def generate_category_briefing(
        self, docs: Union[Dict[str, Any], List[Dict[str, Any]]], 
        category: str, context: Dict[str, Any],
    ):
        """Generate category briefing and yield events"""

        company = context.get('company', 'Unknown')
        industry = context.get('industry', 'Unknown')
        hq_location = context.get('hq_location', 'Unknown')
        company_url = context.get('company_url', '')
        job_id = context.get('job_id')
        
        logger.info(f"Generating {category} briefing for {company} using {len(docs)} documents")

        # Emit briefing start event
        event = {
            "type": "briefing_start",
            "category": category,
            "total_docs": len(docs),
            "step": "Briefing"
        }
        
        if job_id:
            try:
                if job_id in job_status:
                    job_status[job_id]["events"].append(event)
            except Exception as e:
                logger.error(f"Error appending briefing_start event: {e}")
        
        yield event

        # Get category-specific prompt and prepare documents
        category_prompt = self._get_category_prompt(category).format(
            company=company, industry=industry, hq_location=hq_location, company_url=company_url
        )
        formatted_docs = self._prepare_documents(docs)
        
        # Create LCEL chain for briefing generation
        briefing_prompt = ChatPromptTemplate.from_messages([
            ("user", """{category_prompt}

{instruction}

{documents}""")
        ])
        
        chain = briefing_prompt | self.llm | StrOutputParser()
        
        try:
            if job_id and job_id in job_status:
                job_status[job_id]["events"].append({
                    "type": "llm_call",
                    "purpose": f"{category} 摘要生成",
                    "message": f"🤖 LLM调用: 生成 {category} 摘要"
                })
            logger.info("Sending prompt to LLM")

            # Retry with exponential backoff on 429 rate-limit errors
            max_retries = 4
            content = None
            for attempt in range(max_retries):
                try:
                    content = await chain.ainvoke({
                        "category_prompt": category_prompt,
                        "instruction": BRIEFING_ANALYSIS_INSTRUCTION,
                        "documents": formatted_docs
                    })
                    break  # Success
                except Exception as llm_err:
                    err_str = str(llm_err)
                    is_rate_limit = "429" in err_str or "too_many_requests" in err_str.lower() or "rate limit" in err_str.lower()
                    if is_rate_limit and attempt < max_retries - 1:
                        wait = (2 ** attempt) + random.uniform(0, 1)  # 1s, 2s, 4s + jitter
                        logger.warning(f"[briefing] 429 rate limit for {category}, retry {attempt+1}/{max_retries-1} in {wait:.1f}s")
                        await asyncio.sleep(wait)
                    else:
                        raise

            if not content:
                logger.error(f"Empty response from LLM for {category} briefing")
                yield {
                    "type": "error",
                    "stage": "briefing",
                    "error": "Empty response from LLM",
                    "category": category,
                }
                yield {'content': ''}
                return

            # Emit completion event with content
            event = {
                "type": "briefing_complete",
                "category": category,
                "content_length": len(content),
                "content": content.strip(),
                "step": "Briefing"
            }
            
            if job_id:
                try:
                    if job_id in job_status:
                        job_status[job_id]["events"].append(event)
                except Exception as e:
                    logger.error(f"Error appending briefing_complete event: {e}")
            
            yield event
            yield {'content': content.strip()}
        except Exception as e:
            logger.error(f"Error generating {category} briefing: {e}")
            if job_id and job_id in job_status:
                job_status[job_id]["events"].append({
                    "type": "error",
                    "stage": "briefing",
                    "category": category,
                    "error": str(e),
                    "message": f"{category} briefing generation failed"
                })
            raise RuntimeError(f"[briefing] Fatal API error - {category} briefing generation failed: {str(e)}") from e

    async def create_briefings(self, state: ResearchState) -> ResearchState:
        """Create briefings for all categories in parallel."""
        company = state.get('company', 'Unknown Company')
        logger.info(f"Creating section briefings for {company}")
        
        context = {
            "company": company,
            "industry": state.get('industry', 'Unknown'),
            "hq_location": state.get('hq_location', 'Unknown'),
            "job_id": state.get('job_id')
        }
        
        # Mapping of curated data fields to briefing categories
        categories = {
            'news_data': ("news", "news_briefing"),
            'company_data': ("company", "company_briefing"),
            'social_media_data': ("social_media", "social_media_briefing")
        }
        
        briefings = {}

        # Create tasks for parallel processing
        briefing_tasks = []
        for data_field, (cat, briefing_key) in categories.items():
            curated_key = f'curated_{data_field}'
            curated_data = state.get(curated_key, {})
            
            if curated_data:
                logger.info(f"Processing {data_field} with {len(curated_data)} documents")
                briefing_tasks.append({
                    'category': cat,
                    'briefing_key': briefing_key,
                    'data_field': data_field,
                    'curated_data': curated_data
                })
            else:
                logger.info(f"No data available for {data_field}")
                state[briefing_key] = ""

        # Process briefings with adaptive concurrency:
        # Phase 1: all 5 in parallel; Phase 2: retry any 429-failed tasks serially
        if briefing_tasks:
            briefing_semaphore = asyncio.Semaphore(5)  # Start with full parallelism
            failed_tasks: list = []  # Tasks that failed due to 429

            async def process_briefing(task: Dict[str, Any]) -> Dict[str, Any]:
                """Process a single briefing, track 429 failures for later retry."""
                async with briefing_semaphore:
                    result = {'content': ''}

                    async for event in self.generate_category_briefing(
                        task['curated_data'],
                        task['category'],
                        context
                    ):
                        if isinstance(event, dict) and 'content' in event:
                            result = event

                    if result['content']:
                        briefings[task['category']] = result['content']
                        state[task['briefing_key']] = result['content']
                        logger.info(f"Completed {task['data_field']} briefing ({len(result['content'])} characters)")
                    else:
                        raise RuntimeError(f"Empty briefing generated for {task['data_field']}")

                    return {
                        'category': task['category'],
                        'success': True,
                        'length': len(result['content'])
                    }

            # Phase 1: run all tasks in parallel
            phase1_results = await asyncio.gather(
                *[process_briefing(task) for task in briefing_tasks],
                return_exceptions=True
            )

            # Collect failures and check if any are 429-related
            retry_tasks = []
            for task, result in zip(briefing_tasks, phase1_results):
                if isinstance(result, Exception):
                    err_str = str(result)
                    is_rate_limit = "429" in err_str or "too_many_requests" in err_str.lower()
                    if is_rate_limit:
                        logger.warning(f"[briefing] Phase1 429 for {task['category']}, queued for serial retry")
                        retry_tasks.append(task)
                    else:
                        raise result  # Non-429 error: propagate immediately

            # Phase 2: retry failed tasks serially (semaphore=1)
            if retry_tasks:
                logger.info(f"[briefing] Degrading to serial retry for {len(retry_tasks)} task(s)")
                serial_semaphore = asyncio.Semaphore(1)

                async def retry_briefing(task: Dict[str, Any]) -> Dict[str, Any]:
                    async with serial_semaphore:
                        await asyncio.sleep(random.uniform(2, 5))  # Cool-down before retry
                        result = {'content': ''}
                        async for event in self.generate_category_briefing(
                            task['curated_data'],
                            task['category'],
                            context
                        ):
                            if isinstance(event, dict) and 'content' in event:
                                result = event

                        if result['content']:
                            briefings[task['category']] = result['content']
                            state[task['briefing_key']] = result['content']
                            logger.info(f"[retry] Completed {task['data_field']} briefing ({len(result['content'])} characters)")
                        else:
                            raise RuntimeError(f"Empty briefing on retry for {task['data_field']}")

                        return {'category': task['category'], 'success': True, 'length': len(result['content'])}

                retry_results = await asyncio.gather(
                    *[retry_briefing(task) for task in retry_tasks],
                    return_exceptions=True
                )
                for result in retry_results:
                    if isinstance(result, Exception):
                        raise result  # Retry also failed: give up

            results = [r for r in phase1_results if not isinstance(r, Exception)]

            # Log completion statistics
            successful_briefings = len(results) + len(retry_tasks)
            total_length = sum(r['length'] for r in results)
            logger.info(f"Generated {successful_briefings}/{len(briefing_tasks)} briefings with total length {total_length}")

        state['briefings'] = briefings
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        return await self.create_briefings(state)
