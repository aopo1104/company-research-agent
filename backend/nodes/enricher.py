"""
================================================================================
enricher.py - 内容充实阶段 (Stage 6)
================================================================================
获取筛选后文档的完整内容（raw_content）

输入: curated_*_data (仅含URL、摘要、评分)
输出: curated_*_data (每个文档填充raw_content)

实现策略:
  1. 自研爬虫优先 (extract_url_content) - 降低API成本
  2. Tavily Extract 兜底 - 自研爬虫失败时调用
  3. 分批并发处理 - 20个URL/批, 3个批并发
  4. 失败处理 - 保留原摘要，不阻塞流程

流程:
  ① 收集所有URL (来自所有4个curated_*_data)
  ② 调用fetch_raw_content(urls) - 批量获取
  ③ 更新state中的文档 - 填充raw_content字段
  ④ 发送事件给前端 - 进度推送

典型成功率: 87% 自研 + 11% Tavily + 2% 失败
"""

import asyncio
import logging
import os
from typing import Dict, List

from langchain_core.messages import AIMessage
from tavily import AsyncTavilyClient

from ..classes import ResearchState
from ..classes.state import job_status
from ..services.scrape_engine import DomainCircuitBreaker, extract_url_content

logger = logging.getLogger(__name__)


class Enricher:
    """文档充实器 - 获取文档的完整内容"""
    
    def __init__(self) -> None:
        """初始化Enricher，设置Tavily客户端"""
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY environment variable is not set")
        self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
        self.batch_size = 20  # 每批20个URL

    async def fetch_single_content(self, url: str, job_id: str = None,
                                   circuit_breaker: DomainCircuitBreaker = None) -> tuple:
        """获取单个URL的内容 - 自研爬虫优先，Tavily兜底
        
        Args:
            url: 要爬取的URL
            job_id: 任务ID，用于发送事件
            circuit_breaker: 域名熔断器，用于自适应跳过
            
        Returns:
            (url, content, source) 其中source为'custom'/'tavily'/'failed'/'skipped'
        """
        # 熔断检查：如果该域名已连续失败多次，直接跳过
        if circuit_breaker and circuit_breaker.should_skip(url):
            logger.debug(f"[Enricher] Circuit breaker triggered, skipping: {url}")
            return (url, '', 'skipped')

        def _emit(source: str, msg: str):
            if job_id and job_id in job_status:
                try:
                    job_status[job_id]["events"].append({
                        "type": "scrape_source",
                        "source": source,
                        "url": url,
                        "message": msg
                    })
                except Exception:
                    pass

        def _emit_llm_status(msg: str):
            if job_id and job_id in job_status:
                try:
                    job_status[job_id]["events"].append({
                        "type": "llm_status",
                        "used": False,
                        "stage": "enricher_custom_scrape",
                        "url": url,
                        "message": msg
                    })
                except Exception:
                    pass

        # Try custom scraper first
        try:
            _emit_llm_status(f"🤖 LLM状态: 自研爬取未调用LLM ({url[:70]})")
            content = await extract_url_content(url)
            if content and len(content) > 50:
                logger.debug(f"Custom scraper success for {url}")
                _emit("custom", f"自研爬取成功: {url[:70]}")
                if circuit_breaker:
                    circuit_breaker.record_success(url)
                return (url, content, 'custom')
        except Exception as e:
            logger.debug(f"Custom scraper failed for {url}: {e}")

        # Fallback to Tavily extract (15s timeout)
        try:
            result = await asyncio.wait_for(self.tavily_client.extract(url), timeout=15)
            if result and result.get('results'):
                content = result['results'][0].get('raw_content', '')
                _emit("tavily", f"Tavily 兜底: {url[:70]}")
                if circuit_breaker and content:
                    circuit_breaker.record_success(url)
                return (url, content, 'tavily')
        except asyncio.TimeoutError:
            logger.warning(f"Tavily extract timed out (15s) for {url}")
        except Exception as e:
            logger.error(f"Tavily extract fallback failed for {url}: {e}")

        # 全部失败 - 记录到熔断器
        if circuit_breaker:
            circuit_breaker.record_failure(url)
        _emit("failed", f"全部失败: {url[:70]}")
        return (url, '', 'failed')

    async def fetch_raw_content(self, urls: List[str], job_id: str = None,
                               circuit_breaker: DomainCircuitBreaker = None) -> Dict[str, str]:
        """批量获取多个URL的完整内容 - 支持并发、速率限制和自适应熔断
        
        策略:
          1. 分批: 20个URL/批 (避免单次请求过多)
          2. 并发: 最多5个批同时处理 (Semaphore限制)
          3. 熔断: 某域名连续失败3次后自动跳过剩余URL
          4. 结果: {url: content} 字典
        
        Args:
            urls: 要爬取的URL列表
            job_id: 任务ID，用于发送进度事件
            circuit_breaker: 共享的域名熔断器实例
            
        Returns:
            {url: content} 字典，失败的URL返回空字符串
        """
        raw_contents = {}
        
        # Create batches
        batches = [urls[i:i + self.batch_size] for i in range(0, len(urls), self.batch_size)]
        
        # Process batches with rate limiting
        semaphore = asyncio.Semaphore(5)  # Limit concurrent batches to 5
        
        async def process_batch(batch_urls: List[str]) -> List[tuple]:
            async with semaphore:
                tasks = [self.fetch_single_content(url, job_id=job_id,
                                                  circuit_breaker=circuit_breaker)
                         for url in batch_urls]
                return await asyncio.gather(*tasks)

        # Process all batches
        batch_results = await asyncio.gather(*[process_batch(batch) for batch in batches])

        # Combine results from all batches, track source stats
        custom_hits = 0
        tavily_hits = 0
        failed_hits = 0
        skipped_hits = 0
        for batch in batch_results:
            for url, content, source in batch:
                raw_contents[url] = content
                if source == 'custom':
                    custom_hits += 1
                elif source == 'tavily':
                    tavily_hits += 1
                elif source == 'skipped':
                    skipped_hits += 1
                else:
                    failed_hits += 1

        logger.info(
            f"[Enricher] 抓取统计: 自研成功={custom_hits}, Tavily兜底={tavily_hits}, "
            f"熔断跳过={skipped_hits}, 失败={failed_hits}, 总计={len(urls)}"
        )
        return raw_contents

    async def enrich_data(self, state: ResearchState) -> ResearchState:
        """Enrich curated documents with raw content."""
        company = state.get('company', 'Unknown Company')
        job_id = state.get('job_id')

        logger.info(f"Starting enrichment for company: {company}, job_id={job_id}")
        msg = [f"📚 Enriching curated data for {company}:"]

        # 创建本次任务的域名熔断器（任务结束自动丢弃，不影响下次）
        # 粒度: 域名+路径前缀，连续失败2次即熔断该路径组
        circuit_breaker = DomainCircuitBreaker(failure_threshold=2)

        # Process each type of curated data
        data_types = {
            'financial_data': '💰 Financial',
            'news_data': '📰 News',
            'industry_data': '🏭 Industry',
            'company_data': '🏢 Company',
            'social_media_data': '📱 Social Media'
        }

        # Create tasks for parallel processing
        enrichment_tasks = []
        for data_field, label in data_types.items():
            curated_field = f'curated_{data_field}'
            curated_docs = state.get(curated_field, {})
            
            if not curated_docs:
                msg.append(f"\n• No curated {label} documents to enrich")
                continue

            # Find documents needing enrichment
            docs_needing_content = {url: doc for url, doc in curated_docs.items()
                                    if not doc.get('raw_content')}
            
            if not docs_needing_content:
                msg.append(f"\n• All {label} documents already have raw content")
                continue
            
            msg.append(f"\n• Enriching {len(docs_needing_content)} {label} documents...")

            # Extract category name from field (e.g., 'curated_financial_data' -> 'financial')
            category = curated_field.replace('curated_', '').replace('_data', '')
            
            enrichment_tasks.append({
                'field': curated_field,
                'label': label,
                'category': category,
                'docs': docs_needing_content,
                'curated_docs': curated_docs
            })

        # Emit enrichment start event
        if enrichment_tasks and job_id:
            try:
                if job_id in job_status:
                    job_status[job_id]["events"].append({
                        "type": "enrichment",
                        "message": f"Enriching {len(enrichment_tasks)} categories"
                    })
            except Exception as e:
                logger.error(f"Error appending enrichment event: {e}")
        
        # Process all categories in parallel
        if enrichment_tasks:
            async def process_category(task):
                try:
                    raw_contents = await self.fetch_raw_content(
                        list(task['docs'].keys()), job_id=job_id,
                        circuit_breaker=circuit_breaker)
                    
                    enriched_count = 0
                    for url, content in raw_contents.items():
                        if not content:
                            continue
                        # 只有当抓到的内容比文档已有的 content 更长时才覆盖
                        # 避免用 170 字的 meta 覆盖 Tavily 搜索结果中更丰富的摘要
                        existing_content = task['curated_docs'][url].get('content', '')
                        if len(content) > len(existing_content):
                            task['curated_docs'][url]['raw_content'] = content
                            enriched_count += 1
                        else:
                            logger.debug(
                                f"[Enricher] Skipped overwrite for {url}: "
                                f"scraped={len(content)} chars < existing={len(existing_content)} chars"
                            )

                    failed_count = len(task['docs']) - enriched_count
                    if failed_count and job_id and job_id in job_status:
                        job_status[job_id]["events"].append({
                            "type": "stage_warning",
                            "stage": "extract",
                            "category": task['category'],
                            "failed": failed_count,
                            "total": len(task['docs']),
                            "message": f"Extract failed for {failed_count}/{len(task['docs'])} {task['label']} documents"
                        })

                    # Update state with enriched documents
                    state[task['field']] = task['curated_docs']
                    
                    return {
                        'label': task['label'], 
                        'category': task['category'],
                        'enriched': enriched_count, 
                        'total': len(task['docs'])
                    }
                except Exception as e:
                    logger.error(f"Error processing category {task['label']}: {e}")
                    if job_id and job_id in job_status:
                        job_status[job_id]["events"].append({
                            "type": "error",
                            "stage": "extract",
                            "category": task['category'],
                            "error": str(e),
                            "message": f"Extract stage failed for {task['label']} documents"
                        })
                    return {
                        'label': task['label'], 
                        'category': task['category'],
                        'enriched': 0, 
                        'total': len(task['docs'])
                    }

            # Process all categories in parallel
            results = await asyncio.gather(*[process_category(task) for task in enrichment_tasks])
            
            # Add summary to message and emit enrichment completion events
            for result in results:
                msg.append(f"\n  ✓ {result['label']}: {result['enriched']}/{result['total']} documents enriched")
                
                # Emit enrichment completion event for each category
                if job_id:
                    try:
                        if job_id in job_status:
                            job_status[job_id]["events"].append({
                                "type": "enrichment",
                                "category": result['category'],  # Use category instead of label
                                "enriched": result['enriched'],
                                "total": result['total'],
                                "message": f"Enriched {result['enriched']}/{result['total']} {result['label']} documents"
                            })
                    except Exception as e:
                        logger.error(f"Error appending enrichment completion event: {e}")

            # 输出熔断器汇总：哪些路径组被熔断了
            breaker_summary = circuit_breaker.get_summary()
            if breaker_summary:
                broken_keys = [
                    f"{key}(失败{s['failures']}次)"
                    for key, s in breaker_summary.items()
                    if s['failures'] > 0
                ]
                if broken_keys:
                    logger.info(f"[Enricher] 熔断路径: {', '.join(broken_keys)}")

        # Update state with enrichment message
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        try:
            return await self.enrich_data(state)
        except Exception as e:
            logger.error(f"Error in enrichment process: {e}")
            return state
