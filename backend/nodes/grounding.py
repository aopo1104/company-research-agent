import logging
import os

from langchain_core.messages import AIMessage
from tavily import AsyncTavilyClient

from ..classes import InputState, ResearchState
from ..classes.state import job_status
from ..utils.url_filters import is_low_value_url
from ..services.scrape_engine import crawl_site

logger = logging.getLogger(__name__)

class GroundingNode:
    """Gathers initial grounding data about the company."""
    
    def __init__(self) -> None:
        self.tavily_client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    def _emit_event(self, job_id: str | None, event: dict) -> None:
        if not job_id:
            return

        try:
            if job_id in job_status:
                job_status[job_id]["events"].append(event)
        except Exception as e:
            logger.error(f"Error appending event {event.get('type')}: {e}")

    async def initial_search(self, state: InputState):
        """Initial search and yield events"""
        company = state.get('company', 'Unknown Company')
        job_id = state.get('job_id')
        msg = f"🎯 Initiating research for {company}...\n"
        
        # Emit initialization event
        event = {
            "type": "research_init",
            "company": company,
            "message": f"Initiating research for {company}",
            "step": "Initializing"
        }
        
        self._emit_event(job_id, event)
        
        yield event

        site_scrape = {}

        # Only attempt extraction if we have a URL
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
                site_scrape = await crawl_site(url, max_pages=50, max_depth=1)

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
                    site_extraction = await self.tavily_client.crawl(
                        url=url, 
                        instructions="Find any pages that will help us understand the company's business, products, services, and any other relevant information.",
                        max_depth=1, 
                        max_breadth=50, 
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
