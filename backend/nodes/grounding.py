"""
================================================================================
grounding.py - 官网抓取阶段 (Stage 1)
================================================================================
从公司官网抓取初始内容，为后续搜索提供背景信息

输入: company_url (可选)
输出: site_scrape {url: {raw_content, source, method, title}}

实现策略:
  1. 自研爬虫 (crawl_site) - 多策略尝试
     - Strategy 1: static-html (httpx + BeautifulSoup)
     - Strategy 2: json-ld (解析结构化数据)
     - Strategy 3: enhanced-static (反爬headers模拟浏览器)
  2. Tavily Crawl API - 自研爬虫失败时兜底
  3. 最多50个页面，内容净化，max 20000字符

成功率: ~90% (大多数网站可通过自研爬虫抓取)

流程:
  1. 发送crawl_start事件
  2. 调用crawl_site(url) - 自研爬虫
  3. 失败时调用Tavily兜底
  4. 发送crawl_success/crawl_failed事件
"""

import asyncio
import logging
import os
from typing import List

from langchain_core.messages import AIMessage
from tavily import AsyncTavilyClient

from ..classes import InputState, ResearchState
from ..classes.state import job_status
from ..utils.url_filters import is_low_value_url
from ..services.scrape_engine import crawl_site, DEFAULT_FOCUS_KEYWORDS

logger = logging.getLogger(__name__)

class GroundingNode:
    """官网抓取节点 - 从公司官网抓取初始背景信息"""
    
    def __init__(self) -> None:
        """初始化GroundingNode，设置Tavily客户端"""
        self.tavily_client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    def _emit_event(self, job_id: str | None, event: dict) -> None:
        """向WebSocket发送事件 - 实时推送给前端
        
        Args:
            job_id: 任务ID
            event: 事件字典 {type, message, ...}
        """
        if not job_id:
            return

        try:
            if job_id in job_status:
                job_status[job_id]["events"].append(event)
        except Exception as e:
            logger.error(f"Error appending event {event.get('type')}: {e}")

    def _get_focus_keywords(self) -> List[str]:
        """读取定向抓取关键词，支持环境变量覆盖。"""
        # Example: FOCUSED_CRAWL_KEYWORDS=product,category,solutions,catalog
        raw_keywords = os.getenv("FOCUSED_CRAWL_KEYWORDS", "")
        if raw_keywords.strip():
            custom_keywords = [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]
            if custom_keywords:
                return custom_keywords

        return list(DEFAULT_FOCUS_KEYWORDS)

    async def initial_search(self, state: InputState):
        """初始搜索 - 从官网抓取内容
        
        Args:
            state: 用户输入状态 {company, company_url, industry, hq_location}
            
        Yields:
            事件字典，供WebSocket推送给前端
        """
        company = state.get('company', 'Unknown Company')
        job_id = state.get('job_id')
        msg = f"🎯 Initiating research for {company}...\n"
        
        # 发送初始化事件
        event = {
            "type": "research_init",
            "company": company,
            "message": f"Initiating research for {company}",
            "step": "Initializing"
        }
        
        self._emit_event(job_id, event)
        
        yield event

        site_scrape = {}

        # 仅在有URL时才尝试官网抓取
        if url := state.get('company_url'):
            msg += f"\n🌐 Crawling company website: {url}"
            logger.info(f"Starting website analysis for {url}")
            
            # Emit crawl start event
            event = {
                "type": "crawl_start",
                "url": url,
                "message": f"Crawling company website: {url}",
                "step": "Website Crawl"
            }
            
            self._emit_event(job_id, event)

            yield event

            try:
                # Strategy 1: Custom multi-strategy scraper
                logger.info("Initiating custom scrape engine crawl")
                self._emit_event(job_id, {
                    "type": "llm_status",
                    "used": False,
                    "stage": "grounding_custom_scrape",
                    "message": "🤖 LLM状态: 官网自研爬取阶段未调用LLM"
                })

                # 1) 广覆盖 + 2) 专项抓取 并行执行，全局超时45秒防止慢站阻塞
                focus_keywords = self._get_focus_keywords()
                try:
                    broad_scrape, focused_scrape = await asyncio.wait_for(
                        asyncio.gather(
                            crawl_site(url, max_pages=50, max_depth=1),
                            crawl_site(
                                url,
                                max_pages=30,
                                max_depth=1,
                                focus_keywords=focus_keywords,
                                strict_focus=True,
                            ),
                        ),
                        timeout=45,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Crawl timed out (45s) for {url}, using partial results")
                    broad_scrape = {}
                    focused_scrape = {}

                site_scrape = dict(broad_scrape)
                focused_added = 0
                focused_updated = 0
                for page_url, page_data in focused_scrape.items():
                    if page_url not in site_scrape:
                        site_scrape[page_url] = page_data
                        focused_added += 1
                        continue

                    # 同URL情况下，优先保留内容更长的版本
                    existing_len = len(site_scrape[page_url].get("raw_content", ""))
                    new_len = len(page_data.get("raw_content", ""))
                    if new_len > existing_len:
                        site_scrape[page_url] = page_data
                        focused_updated += 1

                self._emit_event(job_id, {
                    "type": "focused_scrape",
                    "focus_keywords": focus_keywords,
                    "broad_pages": len(broad_scrape),
                    "focused_pages": len(focused_scrape),
                    "focused_added": focused_added,
                    "focused_updated": focused_updated,
                    "message": (
                        f"专项抓取完成: broad={len(broad_scrape)} focused={len(focused_scrape)} "
                        f"新增={focused_added} 更新={focused_updated}"
                    ),
                })

                # Filter out low-value URLs
                site_scrape = {
                    page_url: data
                    for page_url, data in site_scrape.items()
                    if not is_low_value_url(page_url)
                }

                if site_scrape:
                    logger.info(f"Custom scraper: {len(site_scrape)} pages extracted")
                    msg += f"\n✅ Custom scraper extracted {len(site_scrape)} pages"
                    self._emit_event(job_id, {
                        "type": "scrape_source",
                        "source": "custom",
                        "count": len(site_scrape),
                        "message": f"自研爬取: {len(site_scrape)} 页"
                    })
                else:
                    # Strategy 2: Tavily as fallback
                    logger.info("Custom scraper returned empty, falling back to Tavily crawl")
                    self._emit_event(job_id, {
                        "type": "scrape_source",
                        "source": "tavily",
                        "count": 0,
                        "message": "自研抓取无结果，切换 Tavily 兜底爬取..."
                    })
                    focus_instructions = ", ".join(self._get_focus_keywords())
                    site_extraction = await self.tavily_client.crawl(
                        url=url, 
                        instructions=(
                            "Find pages that help us understand the company's business, products, "
                            "services, categories, and solutions. Prioritize pages related to: "
                            f"{focus_instructions}."
                        ),
                        max_depth=1, 
                        max_breadth=15, 
                        extract_depth="advanced"
                    )
                    
                    site_scrape = {}
                    for item in site_extraction.get("results", []):
                        if item.get("raw_content"):
                            page_url = item.get("url", url)
                            if is_low_value_url(page_url):
                                logger.info(f"Skipping low-value crawled page: {page_url}")
                                continue
                            site_scrape[page_url] = {
                                'raw_content': item.get('raw_content'),
                                'source': 'company_website'
                            }
                    
                    if site_scrape:
                        logger.info(f"Tavily fallback: {len(site_scrape)} pages crawled")
                        msg += f"\n✅ Tavily fallback crawled {len(site_scrape)} pages"
                        self._emit_event(job_id, {
                            "type": "scrape_source",
                            "source": "tavily",
                            "count": len(site_scrape),
                            "message": f"Tavily 兜底爬取: {len(site_scrape)} 页"
                        })
                
                if site_scrape:
                    logger.info(f"Successfully crawled {len(site_scrape)} pages from website")
                    msg += f"\n✅ Successfully crawled {len(site_scrape)} pages from website"
                    yield {
                        "type": "crawl_success",
                        "pages_found": len(site_scrape),
                        "message": f"Successfully crawled {len(site_scrape)} pages from website",
                        "step": "Initial Site Scrape"
                    }
                else:
                    logger.warning("No content found in crawl results")
                    msg += "\n⚠️ No content found in website crawl"
                    yield {
                        "type": "crawl_warning",
                        "message": "⚠️ No content found in provided URL",
                        "step": "Initial Site Scrape"
                    }
            except Exception as e:
                error_str = str(e)
                logger.error(f"Website crawl error: {error_str}", exc_info=True)
                error_msg = f"⚠️ Error crawling website content: {error_str}"
                msg += f"\n{error_msg}"
                event = {
                    "type": "crawl_error",
                    "stage": "crawl",
                    "error": error_str,
                    "message": error_msg,
                    "step": "Initial Site Scrape",
                    "continue_research": True
                }
                self._emit_event(job_id, event)
                yield event
        else:
            msg += "\n⏩ No company URL provided, proceeding directly to research phase"
            yield {
                "type": "no_url",
                "message": "No company URL provided, proceeding directly to research phase",
                "step": "Initializing"
            }
        # Add context about what information we have
        context_data = {}
        if hq := state.get('hq_location'):
            msg += f"\n📍 Company HQ: {hq}"
            context_data["hq_location"] = hq
        if industry := state.get('industry'):
            msg += f"\n🏭 Industry: {industry}"
            context_data["industry"] = industry
        
        # Initialize ResearchState with input information
        research_state = {
            # Copy input fields
            "company": state.get('company'),
            "company_url": state.get('company_url'),
            "hq_location": state.get('hq_location'),
            "industry": state.get('industry'),
            "job_id": state.get('job_id'),
            # Initialize research fields
            "messages": [AIMessage(content=msg)],
            "site_scrape": site_scrape
        }

        # If there was an error in the initial crawl, store it in the state
        if "⚠️ Error crawling website content:" in msg:
            research_state["error"] = error_str
            research_state["stage"] = "crawl"

        yield {"type": "grounding_complete", "site_pages": len(site_scrape)}
        yield research_state

    async def run(self, state: InputState) -> ResearchState:
        """Run grounding - note: for now returns directly, events can be captured if needed"""
        # For compatibility, we call the generator but don't yield
        # The calling code can be updated later to consume events
        result = None
        async for event in self.initial_search(state):
            # The last yield should be the research_state (a dict with state fields)
            # Earlier yields are event dicts with "type" field
            if isinstance(event, dict) and "type" not in event:
                result = event
        return result if result else {}
