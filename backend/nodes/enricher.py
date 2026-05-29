import asyncio
import logging
import os
from typing import Dict, List

from langchain_core.messages import AIMessage
from tavily import AsyncTavilyClient

from ..classes import ResearchState
from ..classes.state import job_status
from ..services.scrape_engine import extract_url_content

logger = logging.getLogger(__name__)


class Enricher:
    """Enriches curated documents with raw content."""
    
    def __init__(self) -> None:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY environment variable is not set")
        self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
        self.batch_size = 20

    async def fetch_single_content(self, url: str, job_id: str = None) -> tuple:
        """Fetch raw content for a single URL using custom scraper, Tavily as fallback.
        Returns (url, content, source) where source is 'custom', 'tavily', or 'failed'."""
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
                return (url, content, 'custom')
        except Exception as e:
            logger.debug(f"Custom scraper failed for {url}: {e}")

        # Fallback to Tavily extract
        try:
            result = await self.tavily_client.extract(url)
            if result and result.get('results'):
                _emit("tavily", f"Tavily 兜底: {url[:70]}")
                return (url, result['results'][0].get('raw_content', ''), 'tavily')
        except Exception as e:
            logger.error(f"Tavily extract fallback failed for {url}: {e}")
            _emit("failed", f"全部失败: {url[:70]}")
            return (url, '', 'failed')
        _emit("failed", f"全部失败: {url[:70]}")
        return (url, '', 'failed')

    async def fetch_raw_content(self, urls: List[str], job_id: str = None) -> Dict[str, str]:
        """Fetch raw content for multiple URLs in parallel with rate limiting."""
        raw_contents = {}
        
        # Create batches
        batches = [urls[i:i + self.batch_size] for i in range(0, len(urls), self.batch_size)]
        
        # Process batches with rate limiting
        semaphore = asyncio.Semaphore(3)  # Limit concurrent batches to 3
        
        async def process_batch(batch_urls: List[str]) -> List[tuple]:
            async with semaphore:
                tasks = [self.fetch_single_content(url, job_id=job_id) for url in batch_urls]
                return await asyncio.gather(*tasks)

        # Process all batches
        batch_results = await asyncio.gather(*[process_batch(batch) for batch in batches])

        # Combine results from all batches, track source stats
        custom_hits = 0
        tavily_hits = 0
        failed_hits = 0
        for batch in batch_results:
            for url, content, source in batch:
                raw_contents[url] = content
                if source == 'custom':
                    custom_hits += 1
                elif source == 'tavily':
                    tavily_hits += 1
                else:
                    failed_hits += 1

        logger.info(
            f"[Enricher] 抓取统计: 自研成功={custom_hits}, Tavily兜底={tavily_hits}, 失败={failed_hits}, 总计={len(urls)}"
        )
        return raw_contents

    async def enrich_data(self, state: ResearchState) -> ResearchState:
        """Enrich curated documents with raw content."""
        company = state.get('company', 'Unknown Company')
        job_id = state.get('job_id')

        logger.info(f"Starting enrichment for company: {company}, job_id={job_id}")
        msg = [f"📚 Enriching curated data for {company}:"]

        # Process each type of curated data
        data_types = {
            'financial_data': '💰 Financial',
            'news_data': '📰 News',
            'industry_data': '🏭 Industry',
            'company_data': '🏢 Company'
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
                    raw_contents = await self.fetch_raw_content(list(task['docs'].keys()), job_id=job_id)
                    
                    enriched_count = 0
                    for url, content in raw_contents.items():
                        if content:  # Only add non-empty content
                            task['curated_docs'][url]['raw_content'] = content
                            enriched_count += 1

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

        # Update state with enrichment message
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        try:
            return await self.enrich_data(state)
        except Exception as e:
            logger.error(f"Error in enrichment process: {e}")
            return state
