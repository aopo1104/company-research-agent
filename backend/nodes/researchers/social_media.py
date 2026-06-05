from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...classes import ResearchState
from ...prompts import SOCIAL_MEDIA_ANALYZER_QUERY_PROMPT
from .base import BaseResearcher


# Social media platform domains to prioritize in search
SOCIAL_MEDIA_DOMAINS = [
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "xing.com",
    "glassdoor.com",
]


class SocialMediaAnalyzer(BaseResearcher):
    def __init__(self) -> None:
        super().__init__()
        self.analyst_type = "social_media_analyzer"
        self._use_general_search = False

    def _get_search_params(self) -> Dict[str, Any]:
        """Override search params to include social media domains and more results"""
        if self._use_general_search:
            # General search without domain restriction
            return {
                "search_depth": "basic",
                "include_raw_content": True,
                "max_results": 5,
            }
        return {
            "search_depth": "advanced",
            "include_raw_content": True,
            "max_results": 8,
            "include_domains": SOCIAL_MEDIA_DOMAINS,
        }
    
    async def analyze(self, state: ResearchState):
        """Analyze social media presence and yield events"""
        company = state.get('company', 'Unknown Company')
        
        # Generate search queries and yield events
        queries = []
        async for event in self.generate_queries(state, SOCIAL_MEDIA_ANALYZER_QUERY_PROMPT):
            yield event
            if event.get("type") == "queries_complete":
                queries = event.get("queries", [])
        
        # Log subqueries
        subqueries_msg = "🔍 Subqueries for social media analysis:\n" + "\n".join([f"• {query}" for query in queries])
        state.setdefault('messages', []).append(AIMessage(content=subqueries_msg))
        
        # Start with site scrape data
        social_media_data = dict(state.get('site_scrape', {}))
        
        # Search with social media domain restriction (focused search)
        documents = {}
        async for event in self.search_documents(state, queries):
            yield event
            if event.get("type") == "search_complete":
                documents = event.get("merged_docs", {})
        
        social_media_data.update(documents)

        # Also do a general search without domain restriction for broader mentions
        # (reviews, community discussions, forums)
        self._use_general_search = True
        general_docs = {}
        async for event in self.search_documents(state, queries[:2]):
            if event.get("type") == "search_complete":
                general_docs = event.get("merged_docs", {})
        self._use_general_search = False

        social_media_data.update(general_docs)
        
        # Update state
        completion_msg = f"📱 Social Media Analyzer found {len(social_media_data)} documents for {company}"
        state.setdefault('messages', []).append(AIMessage(content=completion_msg))
        state['social_media_data'] = social_media_data
        
        yield {"type": "analysis_complete", "data_type": "social_media_data", "count": len(social_media_data)}
        yield {'message': [completion_msg], 'social_media_data': social_media_data}

    async def run(self, state: ResearchState):
        """Run analysis and yield all events"""
        async for event in self.analyze(state):
            yield event
